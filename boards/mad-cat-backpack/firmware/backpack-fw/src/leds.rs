//! The eight LEDs: plain pins, dimmed in software (see `backpack_core::dim`).
//!
//! Each LED is wired 3.3 V -> 330 ohm -> LED -> XIAO pin, as on the maker's
//! board, so a pin driven LOW lights its LED and a pin left HIGH (or
//! released) leaves it dark.
//!
//! On the XIAO ESP32-C3 the pin for tooth 1 (D9, GPIO9) is also the module's
//! BOOT button, which shorts the pin to ground when pressed. That pin is
//! therefore driven open-drain (it only ever pulls low, so a press can never
//! short a driven-high pin), and the button is read once per dimming frame by
//! releasing the pin for a few microseconds.

use backpack_core::{
    LED_COUNT, Levels,
    dim::{SLICES, slice_mask, slice_us},
};
use esp_hal::{
    gpio::{AnyPin, DriveMode, Flex, Level, OutputConfig, Pull},
    time::Instant,
};

pub struct Leds<'d> {
    pins: [Flex<'d>; LED_COUNT],
    /// Index of the LED whose pin is shared with the BOOT button (C3 only).
    shared: Option<usize>,
    levels: Levels,
    slice: u8,
    slice_end_us: u64,
    button_low: bool,
}

fn now_us() -> u64 {
    Instant::now().duration_since_epoch().as_micros()
}

impl<'d> Leds<'d> {
    pub fn new(pins: [AnyPin<'d>; LED_COUNT], shared: Option<usize>) -> Self {
        let pins = pins.map(Flex::new);
        let mut leds = Self {
            pins,
            shared,
            levels: [0; LED_COUNT],
            slice: 0,
            slice_end_us: now_us(),
            button_low: false,
        };
        for (i, p) in leds.pins.iter_mut().enumerate() {
            // Release any hold left by the last power-off (a pad hold survives
            // deep sleep and the reset that ends it).
            p.set_pad_hold(false);
            p.set_level(Level::High);
            if Some(i) == shared {
                p.apply_output_config(
                    &OutputConfig::default()
                        .with_drive_mode(DriveMode::OpenDrain)
                        .with_pull(Pull::Up),
                );
                p.set_input_enable(true);
            } else {
                p.apply_output_config(&OutputConfig::default());
            }
            p.set_output_enable(true);
        }
        leds
    }

    /// New levels; shown from the next dimming slice on.
    pub fn set(&mut self, levels: Levels) {
        self.levels = levels;
    }

    /// The BOOT button as last sampled (C3 only: there it shares a pin with an LED).
    pub fn shared_button_down(&self) -> bool {
        self.button_low
    }

    /// Call as often as possible: moves to the next dimming slice when the
    /// current one is over.
    pub fn service(&mut self) {
        let now = now_us();
        if now < self.slice_end_us {
            return;
        }
        self.slice = (self.slice + 1) % SLICES;
        if self.slice == 0 {
            self.sample_button();
        }
        let mask = slice_mask(&self.levels, self.slice);
        for (i, p) in self.pins.iter_mut().enumerate() {
            // LED on = pin low
            p.set_level(if mask & (1 << i) != 0 { Level::Low } else { Level::High });
        }
        // If the loop was held up (an I2C transfer), start the next slice
        // from now rather than trying to catch up.
        let start = if now - self.slice_end_us > 1_000 { now } else { self.slice_end_us };
        self.slice_end_us = start + slice_us(self.slice) as u64;
    }

    fn sample_button(&mut self) {
        if let Some(i) = self.shared {
            let p = &mut self.pins[i];
            p.set_level(Level::High); // release: the pull-ups bring it high unless BOOT is pressed
            let t0 = now_us();
            while now_us() - t0 < 5 {}
            self.button_low = p.is_low();
        }
    }

    /// All LEDs dark, and the pins held there through deep sleep.
    pub fn blank_and_hold(&mut self) {
        for p in self.pins.iter_mut() {
            p.set_level(Level::High);
            p.set_pad_hold(true);
        }
    }
}
