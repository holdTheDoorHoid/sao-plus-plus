//! A software ("bit-banged") I2C controller for the private LED-driver bus.
//!
//! Why software: the XIAO ESP32-C3 has only ONE I2C peripheral, and on all
//! three XIAOs that peripheral is already busy being the badge's target on
//! D4/D5. So the LED driver on D10/D3 is driven by toggling two pins by
//! hand. Using the same code on the C6 and S3 keeps one tested path.
//!
//! The pins are open-drain: "high" means *let go* (the board's 1.3 kOhm
//! pull-ups R4/R5 pull the line up), "low" means pull to ground. The
//! hardware side only has to provide [`OpenDrainLines`]; everything about
//! the protocol is here and is tested against a simulated target device.
//!
//! Timing: with the firmware's 2 us half-bit delay a bit takes a little over
//! 4 us, so about 200-250 kHz, under the IS31FL3731's 400 kHz limit
//! (datasheet: t_LOW >= 1.3 us, t_HIGH >= 0.6 us). One full 144-LED update
//! (147 bytes) takes roughly 6-7 ms. Not measured.

use embedded_hal::i2c::{
    Error as I2cError, ErrorKind, ErrorType, I2c, NoAcknowledgeSource, Operation, SevenBitAddress,
};

/// The two bus lines, as seen by the controller.
pub trait OpenDrainLines {
    /// `true` releases SDA (pulled up), `false` pulls it low.
    fn set_sda(&mut self, high: bool);
    /// `true` releases SCL, `false` pulls it low.
    fn set_scl(&mut self, high: bool);
    /// Level actually on the SDA line.
    fn sda(&mut self) -> bool;
    /// Level actually on the SCL line (a target may hold it low to stretch).
    fn scl(&mut self) -> bool;
    /// Wait half a clock period.
    fn delay(&mut self);
}

/// How many polls to wait for SCL to rise before giving up (clock
/// stretching, or a shorted line). The IS31FL3731 does not stretch.
pub const SCL_WAIT_POLLS: u32 = 1_000;

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum Error {
    /// Nobody acknowledged.
    Nack(NoAcknowledgeSource),
    /// SCL did not go high when released, or SDA stayed low: something is
    /// holding the bus.
    Bus,
}

impl I2cError for Error {
    fn kind(&self) -> ErrorKind {
        match self {
            Error::Nack(s) => ErrorKind::NoAcknowledge(*s),
            Error::Bus => ErrorKind::Bus,
        }
    }
}

pub struct BitBangI2c<L> {
    lines: L,
}

impl<L: OpenDrainLines> BitBangI2c<L> {
    /// Takes the lines in any state and releases both.
    pub fn new(mut lines: L) -> Self {
        lines.set_sda(true);
        lines.set_scl(true);
        Self { lines }
    }

    pub fn lines(&mut self) -> &mut L {
        &mut self.lines
    }

    /// Clear a target that was left halfway through a byte (for example by
    /// a reset of the XIAO mid-transfer) and is holding SDA low: clock up to
    /// nine pulses until it lets go, then send a STOP.
    pub fn recover(&mut self) -> Result<(), Error> {
        self.lines.set_sda(true);
        for _ in 0..9 {
            if self.lines.sda() {
                break;
            }
            self.lines.set_scl(false);
            self.lines.delay();
            self.scl_high()?;
            self.lines.delay();
        }
        self.lines.set_scl(false);
        self.lines.delay();
        self.stop()?;
        if self.lines.sda() {
            Ok(())
        } else {
            Err(Error::Bus)
        }
    }

    fn scl_high(&mut self) -> Result<(), Error> {
        self.lines.set_scl(true);
        for _ in 0..SCL_WAIT_POLLS {
            if self.lines.scl() {
                return Ok(());
            }
        }
        Err(Error::Bus)
    }

    /// START, or repeated START if a transfer is already running. Leaves
    /// SCL low.
    fn start(&mut self) -> Result<(), Error> {
        self.lines.set_sda(true);
        self.lines.delay();
        self.scl_high()?;
        if !self.lines.sda() {
            return Err(Error::Bus);
        }
        self.lines.delay();
        self.lines.set_sda(false);
        self.lines.delay();
        self.lines.set_scl(false);
        Ok(())
    }

    /// STOP. Expects SCL low; leaves the bus idle (both high).
    fn stop(&mut self) -> Result<(), Error> {
        self.lines.set_sda(false);
        self.lines.delay();
        let r = self.scl_high();
        self.lines.delay();
        self.lines.set_sda(true);
        self.lines.delay();
        r
    }

    /// Send one byte, MSB first. Returns whether the target acknowledged.
    fn write_byte(&mut self, byte: u8) -> Result<bool, Error> {
        for bit in (0..8).rev() {
            self.lines.set_sda(byte & (1 << bit) != 0);
            self.lines.delay();
            self.scl_high()?;
            self.lines.delay();
            self.lines.set_scl(false);
        }
        self.lines.set_sda(true);
        self.lines.delay();
        self.scl_high()?;
        let ack = !self.lines.sda();
        self.lines.delay();
        self.lines.set_scl(false);
        Ok(ack)
    }

    /// Receive one byte, then ACK it (`ack == true`) or NACK it.
    fn read_byte(&mut self, ack: bool) -> Result<u8, Error> {
        let mut byte = 0u8;
        self.lines.set_sda(true);
        for _ in 0..8 {
            self.lines.delay();
            self.scl_high()?;
            byte = (byte << 1) | self.lines.sda() as u8;
            self.lines.delay();
            self.lines.set_scl(false);
        }
        self.lines.set_sda(!ack);
        self.lines.delay();
        self.scl_high()?;
        self.lines.delay();
        self.lines.set_scl(false);
        self.lines.set_sda(true);
        Ok(byte)
    }

    fn run(&mut self, address: u8, ops: &mut [Operation<'_>]) -> Result<(), Error> {
        let mut last_was_read: Option<bool> = None;
        let n = ops.len();
        for i in 0..n {
            let is_read = matches!(ops[i], Operation::Read(_));
            // embedded-hal: a START + address only when the direction changes.
            if last_was_read != Some(is_read) {
                self.start()?;
                if !self.write_byte((address << 1) | is_read as u8)? {
                    return Err(Error::Nack(NoAcknowledgeSource::Address));
                }
            }
            last_was_read = Some(is_read);
            let next_is_read = matches!(ops.get(i + 1), Some(Operation::Read(_)));
            match &mut ops[i] {
                Operation::Write(bytes) => {
                    for &b in bytes.iter() {
                        if !self.write_byte(b)? {
                            return Err(Error::Nack(NoAcknowledgeSource::Data));
                        }
                    }
                }
                Operation::Read(buf) => {
                    let len = buf.len();
                    for (k, b) in buf.iter_mut().enumerate() {
                        // NACK the very last byte of a run of reads.
                        let last = k + 1 == len && !next_is_read;
                        *b = self.read_byte(!last)?;
                    }
                }
            }
        }
        Ok(())
    }
}

impl<L> ErrorType for BitBangI2c<L> {
    type Error = Error;
}

impl<L: OpenDrainLines> I2c<SevenBitAddress> for BitBangI2c<L> {
    fn transaction(&mut self, address: u8, ops: &mut [Operation<'_>]) -> Result<(), Error> {
        let r = self.run(address, ops);
        // Always finish with a STOP, also after an error, so the bus is idle.
        let s = self.stop();
        r.and(s)
    }
}

#[cfg(test)]
pub(crate) mod sim {
    //! A bit-level I2C target that watches the two lines, used to test the
    //! controller above without hardware.
    use super::OpenDrainLines;
    use std::vec::Vec;

    #[derive(Clone, Copy, Debug, PartialEq, Eq)]
    pub enum Event {
        Start,
        Stop,
        /// Address byte (7-bit address << 1 | R/W) and whether we ACKed it.
        Addr(u8, bool),
        Byte(u8),
        /// A byte we sent and whether the controller ACKed it.
        Sent(u8, bool),
    }

    #[derive(Clone, Copy, Debug, PartialEq, Eq)]
    enum Mode {
        Idle,
        Addr,
        Write,
        Read,
        Ignore,
    }

    pub struct SimTarget {
        pub address: u8,
        m_sda: bool,
        m_scl: bool,
        s_sda: bool,
        mode: Mode,
        bit: u8,
        byte: u8,
        cur: u8,
        master_ack: bool,
        in_ack: bool,
        pub read_data: Vec<u8>,
        read_pos: usize,
        pub log: Vec<Event>,
        /// Hold SCL low forever (stuck bus).
        pub scl_stuck_low: bool,
        /// Refuse (NACK) data bytes after this many.
        pub nack_data_after: Option<usize>,
        data_count: usize,
        /// Count of half-bit delays requested.
        pub delays: usize,
    }

    impl SimTarget {
        pub fn new(address: u8) -> Self {
            Self {
                address,
                m_sda: true,
                m_scl: true,
                s_sda: true,
                mode: Mode::Idle,
                bit: 0,
                byte: 0,
                cur: 0,
                master_ack: false,
                in_ack: false,
                read_data: Vec::new(),
                read_pos: 0,
                log: Vec::new(),
                scl_stuck_low: false,
                nack_data_after: None,
                data_count: 0,
                delays: 0,
            }
        }

        /// Start out holding SDA low, as if reset mid-read.
        pub fn stuck_mid_byte(&mut self) {
            self.mode = Mode::Read;
            self.cur = 0;
            self.bit = 1;
            self.s_sda = false;
            self.master_ack = false;
        }

        fn bus_sda(&self) -> bool {
            self.m_sda && self.s_sda
        }
        fn bus_scl(&self) -> bool {
            self.m_scl && !self.scl_stuck_low
        }

        /// Written bytes of every write transfer (between START/STOP),
        /// without the address byte.
        pub fn writes(&self) -> Vec<Vec<u8>> {
            let mut out = Vec::new();
            let mut cur: Option<Vec<u8>> = None;
            for e in &self.log {
                match e {
                    Event::Addr(a, true) if a & 1 == 0 => {
                        if let Some(c) = cur.take() {
                            out.push(c);
                        }
                        cur = Some(Vec::new());
                    }
                    Event::Byte(b) => cur.as_mut().unwrap().push(*b),
                    Event::Stop | Event::Start => {
                        if let Some(c) = cur.take() {
                            out.push(c);
                        }
                    }
                    _ => {}
                }
            }
            if let Some(c) = cur {
                out.push(c);
            }
            out
        }

        fn load_read_byte(&mut self) {
            self.cur = self.read_data.get(self.read_pos).copied().unwrap_or(0xFF);
            self.read_pos += 1;
            self.bit = 0;
            self.s_sda = self.cur & 0x80 != 0;
        }

        fn edge(&mut self, ps: bool, pc: bool) {
            let (s, c) = (self.bus_sda(), self.bus_scl());
            if pc && c && ps != s {
                if !s {
                    self.log.push(Event::Start);
                    self.mode = Mode::Addr;
                    self.in_ack = false;
                    self.bit = 0;
                    self.byte = 0;
                } else {
                    self.log.push(Event::Stop);
                    self.mode = Mode::Idle;
                }
                self.s_sda = true;
                return;
            }
            if !pc && c {
                // Rising SCL: sample.
                match self.mode {
                    Mode::Addr | Mode::Write if self.bit < 8 => {
                        self.byte = (self.byte << 1) | s as u8;
                        self.bit += 1;
                    }
                    Mode::Read if self.bit == 8 => self.master_ack = !s,
                    _ => {}
                }
            }
            if pc && !c {
                // Falling SCL: drive the next thing.
                match self.mode {
                    Mode::Addr | Mode::Write => {
                        if self.bit == 8 && !self.in_ack {
                            self.in_ack = true;
                            if self.mode == Mode::Addr {
                                let ok = self.byte >> 1 == self.address;
                                self.log.push(Event::Addr(self.byte, ok));
                                if ok {
                                    self.s_sda = false;
                                } else {
                                    self.mode = Mode::Ignore;
                                }
                            } else {
                                self.log.push(Event::Byte(self.byte));
                                self.data_count += 1;
                                let refuse =
                                    self.nack_data_after.is_some_and(|n| self.data_count > n);
                                self.s_sda = refuse;
                            }
                        } else if self.bit == 8 {
                            // End of the ACK clock.
                            self.in_ack = false;
                            self.s_sda = true;
                            self.bit = 0;
                            if self.mode == Mode::Addr && self.byte & 1 == 1 {
                                self.mode = Mode::Read;
                                self.load_read_byte();
                            } else {
                                self.mode = Mode::Write;
                            }
                            self.byte = 0;
                        }
                    }
                    Mode::Read => {
                        if self.bit < 8 {
                            self.bit += 1;
                            if self.bit < 8 {
                                self.s_sda = self.cur & (0x80 >> self.bit) != 0;
                            } else {
                                self.s_sda = true; // controller's ACK slot
                            }
                        } else {
                            self.log.push(Event::Sent(self.cur, self.master_ack));
                            if self.master_ack {
                                self.load_read_byte();
                            } else {
                                self.mode = Mode::Ignore;
                                self.s_sda = true;
                            }
                        }
                    }
                    Mode::Idle | Mode::Ignore => {}
                }
            }
        }
    }

    impl OpenDrainLines for SimTarget {
        fn set_sda(&mut self, high: bool) {
            let (ps, pc) = (self.bus_sda(), self.bus_scl());
            self.m_sda = high;
            self.edge(ps, pc);
        }
        fn set_scl(&mut self, high: bool) {
            let (ps, pc) = (self.bus_sda(), self.bus_scl());
            self.m_scl = high;
            self.edge(ps, pc);
        }
        fn sda(&mut self) -> bool {
            self.bus_sda()
        }
        fn scl(&mut self) -> bool {
            self.bus_scl()
        }
        fn delay(&mut self) {
            self.delays += 1;
        }
    }
}

#[cfg(test)]
mod tests {
    use super::sim::{Event, SimTarget};
    use super::*;
    use crate::LED_COUNT;
    use crate::is31fl3731::{self, Is31fl3731, tests::ChipModel};
    use std::vec;

    fn bus() -> BitBangI2c<SimTarget> {
        BitBangI2c::new(SimTarget::new(0x74))
    }

    #[test]
    fn simple_write_is_start_address_bytes_stop() {
        let mut b = bus();
        b.write(0x74, &[0xFD, 0x0B]).unwrap();
        assert_eq!(
            b.lines().log,
            [
                Event::Start,
                Event::Addr(0xE8, true),
                Event::Byte(0xFD),
                Event::Byte(0x0B),
                Event::Stop
            ]
        );
    }

    #[test]
    fn every_byte_value_survives() {
        let mut b = bus();
        let all: std::vec::Vec<u8> = (0..=255).collect();
        b.write(0x74, &all).unwrap();
        assert_eq!(b.lines().writes(), vec![all]);
    }

    #[test]
    fn wrong_address_is_a_nack_and_the_bus_is_left_idle() {
        let mut b = bus();
        assert_eq!(
            b.write(0x75, &[1, 2]),
            Err(Error::Nack(NoAcknowledgeSource::Address))
        );
        let l = b.lines();
        assert_eq!(l.log.last(), Some(&Event::Stop));
        assert!(l.sda() && l.scl());
    }

    #[test]
    fn data_nack_is_reported() {
        let mut b = bus();
        b.lines().nack_data_after = Some(1);
        assert_eq!(
            b.write(0x74, &[1, 2, 3]),
            Err(Error::Nack(NoAcknowledgeSource::Data))
        );
        assert_eq!(b.lines().writes(), vec![vec![1, 2]]);
    }

    #[test]
    fn write_read_uses_a_repeated_start_and_nacks_the_last_byte() {
        let mut b = bus();
        b.lines().read_data = vec![0x12, 0x34, 0x56];
        let mut buf = [0u8; 3];
        b.write_read(0x74, &[0x07], &mut buf).unwrap();
        assert_eq!(buf, [0x12, 0x34, 0x56]);
        assert_eq!(
            b.lines().log,
            [
                Event::Start,
                Event::Addr(0xE8, true),
                Event::Byte(0x07),
                Event::Start,
                Event::Addr(0xE9, true),
                Event::Sent(0x12, true),
                Event::Sent(0x34, true),
                Event::Sent(0x56, false),
                Event::Stop
            ]
        );
    }

    #[test]
    fn consecutive_writes_in_one_transaction_share_one_address() {
        let mut b = bus();
        b.transaction(
            0x74,
            &mut [Operation::Write(&[1]), Operation::Write(&[2, 3])],
        )
        .unwrap();
        assert_eq!(b.lines().writes(), vec![vec![1, 2, 3]]);
    }

    #[test]
    fn stuck_clock_is_a_bus_error_not_a_hang() {
        let mut b = bus();
        b.lines().scl_stuck_low = true;
        assert_eq!(b.write(0x74, &[1]), Err(Error::Bus));
    }

    #[test]
    fn recover_frees_a_target_holding_sda() {
        let mut b = bus();
        b.lines().stuck_mid_byte();
        assert!(!b.lines().sda());
        b.recover().unwrap();
        assert!(b.lines().sda() && b.lines().scl());
        // And the bus works afterwards.
        b.write(0x74, &[9]).unwrap();
        assert_eq!(b.lines().writes().last().unwrap(), &vec![9]);
    }

    #[test]
    fn idle_bus_stays_idle_after_new() {
        let mut b = bus();
        assert!(b.lines().sda() && b.lines().scl());
        assert!(b.lines().log.is_empty());
    }

    /// The whole stack: driver -> bit-banged bus -> simulated wire ->
    /// register model. What reaches the chip must be what the driver meant.
    #[test]
    fn driver_over_bitbang_programs_the_chip_model() {
        let mut d = Is31fl3731::new(bus());
        let pwm: [u8; LED_COUNT] = core::array::from_fn(|i| (i * 7) as u8);
        d.init(&pwm).unwrap();
        d.write_pwm(&[5; LED_COUNT]).unwrap();
        d.set_shutdown(true).unwrap();
        let mut bb = d.release();
        let mut chip = ChipModel::new();
        for w in bb.lines().writes() {
            chip.apply(&w);
        }
        assert_eq!(chip.pwm(0), &[5; LED_COUNT][..]);
        assert_eq!(&chip.frames[0][..18], &[0xFF; 18]);
        assert!(chip.shutdown());
        assert_eq!(chip.function[is31fl3731::REG_CONFIG as usize], 0);
    }

    #[test]
    fn clock_is_slow_enough() {
        // Every SCL high and low phase is separated by at least one delay
        // (2 us in the firmware), well over the chip's 1.3 us / 0.6 us
        // minimums. Count: at least 2 delays per bit.
        let mut b = bus();
        b.write(0x74, &[0; 10]).unwrap();
        let bits = 11 * 9;
        assert!(b.lines().delays >= 2 * bits);
    }
}
