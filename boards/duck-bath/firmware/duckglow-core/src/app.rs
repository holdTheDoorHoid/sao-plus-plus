//! The add-on's behaviour, tied together: registers, fading, WS2812 input,
//! presets and the power switch.
//!
//! The firmware calls [`App::tick`] often (every millisecond or two) with the
//! time and the raw OFF-sense level, passes every badge write to
//! [`App::on_i2c_write`], answers badge reads with [`App::i2c_read`], and
//! hands decoded WS2812 frames to [`App::on_ws2812_frame`]. It shows
//! [`App::brightness`] on the LEDs and carries out the [`Action`]s it is given
//! (write the presets to flash, restart, sleep).

use crate::{
    CHANNELS, CHANNELS_USED,
    fader::{Fader, STEP_MS},
    input::Debounced,
    presets,
    regs::{self, Registers},
    ws2812::{self, Latch},
};

/// The switch must sit on OFF this long before the add-on goes to sleep.
pub const OFF_SETTLE_MS: u32 = 50;

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum Action {
    None,
    /// Write these bytes to the presets area of flash, then report back with
    /// [`App::saved`].
    SavePresets([u8; presets::BLOB_LEN]),
    /// Erase the presets and restart (the maker's board restarts after a
    /// factory reset too).
    FactoryReset,
    /// The switch is on OFF: LEDs are dark; sleep until it moves.
    PowerOff,
}

pub struct App {
    regs: Registers,
    uv: bool,
    faders: [Fader; CHANNELS],
    ws_active: bool,
    out: [u16; CHANNELS],
    next_step: u32,
    off: Debounced,
    stored: Option<[u8; presets::BLOB_LEN]>,
}

impl App {
    /// `uv`: the LED type found at power-on (no red LED answered). `stored`:
    /// the presets bytes read from flash, if any.
    pub fn new(now_ms: u32, uv: bool, stored: Option<&[u8]>, off_at_boot: bool) -> Self {
        let mut regs = Registers::new(uv);
        let mut kept = None;
        match stored.and_then(presets::decode) {
            Some(s) => {
                regs.load_settings(&s, uv);
                regs.set_debug(regs::DBG_OK);
                kept = Some(presets::encode(&s));
            }
            None => regs.set_debug(regs::DBG_NO_PRESETS),
        }
        let faders = core::array::from_fn(|ch| Fader::new(regs.phase(ch)));
        Self {
            regs,
            uv,
            faders,
            ws_active: false,
            out: [0; CHANNELS],
            next_step: now_ms,
            off: Debounced::new(off_at_boot, OFF_SETTLE_MS),
            stored: kept,
        }
    }

    /// Brightness of each channel, 0..=1023 (red, green, blue, background).
    /// Channels this board does not have are always 0.
    pub fn brightness(&self) -> [u16; CHANNELS] {
        let mut o = self.out;
        for v in o.iter_mut().skip(CHANNELS_USED) {
            *v = 0;
        }
        if self.off.level() {
            o = [0; CHANNELS];
        }
        o
    }

    /// True while the LEDs follow WS2812 data instead of fading.
    pub fn ws2812_active(&self) -> bool {
        self.ws_active
    }

    /// True if the firmware should listen for WS2812 data at all (mode auto or
    /// WS2812; in mode I2C it can switch the receiver off).
    pub fn ws2812_wanted(&self) -> bool {
        self.regs.mode_ctrl() != regs::MODE_I2C
    }

    pub fn tick(&mut self, now_ms: u32, off_raw: bool) -> Action {
        self.off.update(off_raw, now_ms);
        if self.off.level() {
            self.out = [0; CHANNELS];
            return Action::PowerOff;
        }
        match self.regs.take_save() {
            regs::SAVE_PRESETS => {
                let blob = presets::encode(&self.regs.settings());
                if self.stored == Some(blob) {
                    // nothing changed: spare the flash, still report success
                    self.regs.set_debug(regs::DBG_UNCHANGED);
                } else {
                    return Action::SavePresets(blob);
                }
            }
            regs::FACTORY_RESET => return Action::FactoryReset,
            _ => {}
        }
        match self.regs.mode_ctrl() {
            regs::MODE_WS2812 => self.ws_active = true,
            regs::MODE_I2C => self.ws_active = false,
            _ => {}
        }
        if !self.ws_active && now_ms.wrapping_sub(self.next_step) as i32 >= 0 {
            self.next_step = self.next_step.wrapping_add(STEP_MS);
            if now_ms.wrapping_sub(self.next_step) as i32 > 0 {
                self.next_step = now_ms.wrapping_add(STEP_MS); // fell behind: do not race to catch up
            }
            for ch in 0..CHANNELS {
                let r = &self.regs;
                self.out[ch] = self.faders[ch].step(r.max(ch), r.min(ch), r.speed(ch), r.phase(ch));
            }
        }
        Action::None
    }

    /// The firmware reports how the flash write went.
    pub fn saved(&mut self, ok: bool) {
        if ok {
            self.stored = Some(presets::encode(&self.regs.settings()));
            self.regs.set_debug(regs::DBG_OK);
        } else {
            self.regs.set_debug(regs::DBG_FLASH_ERROR);
        }
    }

    /// A write from the badge. Any write with data leaves WS2812 mode (the
    /// maker's board does the same), so the new settings show at once.
    pub fn on_i2c_write(&mut self, bytes: &[u8]) {
        if self.regs.write(bytes) > 0 {
            self.regs.set_uv(self.uv);
            self.ws_active = false;
            // a new phase takes effect from the next step, as on the maker's board
        }
    }

    /// Fill `out` with what a badge read gets (from the current register on).
    pub fn i2c_read(&self, out: &mut [u8]) {
        self.regs.read_into(out);
    }

    /// The badge read `n` bytes: move the register number on.
    pub fn i2c_read_done(&mut self, n: usize) {
        self.regs.advance(n);
    }

    /// A high pulse was seen on SAO GPIO2. In auto mode a WS2812-like pulse
    /// switches to WS2812 mode.
    pub fn on_gpio2_pulse(&mut self, high_ns: u32) {
        if self.regs.mode_ctrl() == regs::MODE_AUTO && ws2812::looks_like_ws2812(high_ns) {
            self.ws_active = true;
        }
    }

    /// A whole WS2812 frame (pulse lengths) arrived on SAO GPIO2.
    pub fn on_ws2812_frame(&mut self, pulses: &[(u32, u32)]) {
        if let Some(&(h, _)) = pulses.first() {
            self.on_gpio2_pulse(h);
        }
        if !self.ws_active {
            return;
        }
        if let Some(Latch { rgb, background }) = ws2812::decode(pulses) {
            self.out = [(rgb[0] as u16) << 2, (rgb[1] as u16) << 2, (rgb[2] as u16) << 2, (background as u16) << 2];
        }
    }

    pub fn registers(&self) -> &Registers {
        &self.regs
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::regs::*;
    use std::vec::Vec;

    fn run(app: &mut App, from: u32, to: u32) -> Vec<Action> {
        (from..to).map(|t| app.tick(t, false)).filter(|a| *a != Action::None).collect()
    }

    #[test]
    fn starts_with_factory_breath() {
        let mut a = App::new(0, false, None, false);
        assert_eq!(a.registers().get(REG_DEBUG), DBG_NO_PRESETS);
        a.tick(0, false);
        let b = a.brightness();
        assert_eq!(b[0], 40); // min 10 << 2
        assert_eq!(b[1], 40);
        assert_eq!(b[2], 0);
        run(&mut a, 1, 20 * 300);
        assert!(a.brightness()[0] > 40);
    }

    #[test]
    fn fourth_channel_only_on_jaws() {
        let mut a = App::new(0, false, None, false);
        a.on_i2c_write(&[REG_MAX + 3, 200]);
        a.on_i2c_write(&[REG_SPEED + 3, 0]);
        a.tick(0, false);
        let want = if crate::CHANNELS_USED == 4 { 800 } else { 0 };
        assert_eq!(a.brightness()[3], want);
    }

    #[test]
    fn steady_colour_over_i2c() {
        // the maker's README example: red to full, no fading
        let mut a = App::new(0, false, None, false);
        a.on_i2c_write(&[REG_MAX, 0xFF]);
        a.on_i2c_write(&[REG_SPEED, 0]);
        a.tick(0, false);
        assert_eq!(a.brightness()[0], 1020);
    }

    #[test]
    fn save_flow() {
        let mut a = App::new(0, false, None, false);
        a.on_i2c_write(&[REG_MAX, 1, 2, 3, 4]);
        a.on_i2c_write(&[REG_SAVE, SAVE_PRESETS]);
        let acts = run(&mut a, 0, 5);
        let Action::SavePresets(blob) = acts[0] else { panic!("{acts:?}") };
        a.saved(true);
        assert_eq!(a.registers().get(REG_DEBUG), DBG_OK);
        // saving again without a change does not touch the flash
        a.on_i2c_write(&[REG_SAVE, SAVE_PRESETS]);
        assert!(run(&mut a, 5, 10).is_empty());
        assert_eq!(a.registers().get(REG_DEBUG), DBG_UNCHANGED);
        // and the saved bytes come back at the next power-on
        let b = App::new(0, false, Some(&blob), false);
        assert_eq!(b.registers().max(3), 4);
        assert_eq!(b.registers().get(REG_DEBUG), DBG_OK);
    }

    #[test]
    fn flash_error_is_reported() {
        let mut a = App::new(0, false, None, false);
        a.on_i2c_write(&[REG_SAVE, SAVE_PRESETS]);
        assert!(matches!(a.tick(0, false), Action::SavePresets(_)));
        a.saved(false);
        assert_eq!(a.registers().get(REG_DEBUG), DBG_FLASH_ERROR);
    }

    #[test]
    fn factory_reset() {
        let mut a = App::new(0, false, None, false);
        a.on_i2c_write(&[REG_SAVE, FACTORY_RESET]);
        assert_eq!(a.tick(0, false), Action::FactoryReset);
    }

    #[test]
    fn other_save_values_do_nothing() {
        let mut a = App::new(0, false, None, false);
        a.on_i2c_write(&[REG_SAVE, 7]);
        assert!(run(&mut a, 0, 3).is_empty());
    }

    #[test]
    fn ws2812_auto_mode() {
        let mut a = App::new(0, false, None, false);
        assert!(a.ws2812_wanted());
        let frame: Vec<(u32, u32)> = [0u8, 0, 0x80, 0x10, 0x20, 0x30]
            .iter()
            .flat_map(|&b| (0..8).rev().map(move |i| if b >> i & 1 == 1 { (700, 600) } else { (350, 800) }))
            .collect();
        a.on_ws2812_frame(&frame);
        assert!(a.ws2812_active());
        assert_eq!(a.brightness()[..3], [0x20 << 2, 0x10 << 2, 0x30 << 2]);
        // fading stops while WS2812 is in charge
        run(&mut a, 0, 1000);
        assert_eq!(a.brightness()[0], 0x20 << 2);
        // any I2C write hands control back
        a.on_i2c_write(&[REG_SPEED, 2]);
        assert!(!a.ws2812_active());
    }

    #[test]
    fn i2c_mode_ignores_ws2812() {
        let mut a = App::new(0, false, None, false);
        a.on_i2c_write(&[REG_MODE, MODE_I2C]);
        assert!(!a.ws2812_wanted());
        a.on_ws2812_frame(&[(700, 600); 24]);
        a.tick(0, false);
        assert!(!a.ws2812_active());
    }

    #[test]
    fn ws2812_mode_forced() {
        let mut a = App::new(0, false, None, false);
        a.on_i2c_write(&[REG_MODE, MODE_WS2812]);
        a.tick(0, false);
        assert!(a.ws2812_active());
    }

    #[test]
    fn uv_board() {
        let mut a = App::new(0, true, None, false);
        assert_eq!(a.registers().get(REG_MODE), MODE_UV);
        a.on_i2c_write(&[REG_MODE, 0]);
        assert_eq!(a.registers().get(REG_MODE), MODE_UV);
        a.tick(0, false);
        assert_eq!(a.brightness()[2], 0); // starts at the bottom of its breath
    }

    #[test]
    fn off_switch_darkens_and_sleeps() {
        let mut a = App::new(0, false, None, false);
        a.on_i2c_write(&[REG_SPEED, 0, 0, 0, 0]);
        a.tick(0, false);
        assert!(a.brightness()[0] > 0);
        assert_eq!(a.tick(10, true), Action::None);
        assert_eq!(a.tick(10 + OFF_SETTLE_MS, true), Action::PowerOff);
        assert_eq!(a.brightness(), [0; 4]);
        // a short glitch does not
        let mut b = App::new(0, false, None, false);
        b.tick(0, true);
        assert_eq!(b.tick(OFF_SETTLE_MS - 1, false), Action::None);
    }

    #[test]
    fn read_back_registers() {
        let mut a = App::new(0, false, None, false);
        a.on_i2c_write(&[REG_MAX]);
        let mut out = [0u8; 4];
        a.i2c_read(&mut out);
        assert_eq!(out, DEFAULT_MAX);
        a.i2c_read_done(4);
        a.i2c_read(&mut out);
        assert_eq!(out, DEFAULT_MIN);
    }

    #[test]
    fn steps_every_20_ms() {
        let mut a = App::new(0, false, None, false);
        a.on_i2c_write(&[REG_MAX, 255]);
        a.on_i2c_write(&[REG_MIN, 0]);
        a.on_i2c_write(&[REG_SPEED, 1]);
        let mut changes = 0;
        let mut last = a.brightness()[0];
        for t in 0..2000 {
            a.tick(t, false);
            if a.brightness()[0] != last {
                assert_eq!(t % 20, 0, "changed between steps at {t} ms");
                changes += 1;
                last = a.brightness()[0];
            }
        }
        assert!((60..=100).contains(&changes), "{changes}");
    }
}
