//! A software ("bit-banged") I2C controller for the board's private bus:
//! the touch chip (address 0x28) and whatever is plugged into the maker's
//! second Qwiic socket.
//!
//! Why software: the XIAO ESP32-C3 has only one I2C peripheral and it is
//! busy being the badge's target on D4/D5. Same idea as Do Or Donut.
//!
//! The lines are open-drain: "high" lets go (the board's 1.3 kOhm pull-ups
//! R11/R12 pull the line up), "low" pulls it to ground. The hardware only
//! provides [`Lines`]; the protocol is here and is tested against a
//! simulated target.

pub trait Lines {
    fn set_sda(&mut self, high: bool);
    fn set_scl(&mut self, high: bool);
    fn sda(&mut self) -> bool;
    fn scl(&mut self) -> bool;
    /// Wait half a clock period.
    fn delay(&mut self);
}

/// Polls to wait for SCL to rise (a target may stretch the clock).
pub const SCL_WAIT_POLLS: u32 = 2_000;

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum Error {
    /// Nobody answered at that address (or a byte was refused).
    Nack,
    /// A line is held low by something: the bus is stuck.
    Bus,
}

pub struct BitBang<L> {
    lines: L,
}

impl<L: Lines> BitBang<L> {
    pub fn new(mut lines: L) -> Self {
        lines.set_sda(true);
        lines.set_scl(true);
        Self { lines }
    }

    pub fn lines(&mut self) -> &mut L {
        &mut self.lines
    }

    /// Free a target left halfway through a byte: up to nine clocks, then STOP.
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
        if self.lines.sda() { Ok(()) } else { Err(Error::Bus) }
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

    fn stop(&mut self) -> Result<(), Error> {
        self.lines.set_sda(false);
        self.lines.delay();
        let r = self.scl_high();
        self.lines.delay();
        self.lines.set_sda(true);
        self.lines.delay();
        r
    }

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

    fn read_byte(&mut self, ack: bool) -> Result<u8, Error> {
        self.lines.set_sda(true);
        let mut v = 0u8;
        for _ in 0..8 {
            self.lines.delay();
            self.scl_high()?;
            v = (v << 1) | self.lines.sda() as u8;
            self.lines.delay();
            self.lines.set_scl(false);
        }
        self.lines.set_sda(!ack);
        self.lines.delay();
        self.scl_high()?;
        self.lines.delay();
        self.lines.set_scl(false);
        self.lines.set_sda(true);
        Ok(v)
    }

    fn finish<T>(&mut self, r: Result<T, Error>) -> Result<T, Error> {
        let s = self.stop();
        let v = r?;
        s.map(|_| v)
    }

    /// Write `bytes` to the 7-bit `addr`.
    pub fn write(&mut self, addr: u8, bytes: &[u8]) -> Result<(), Error> {
        self.start()?;
        let r = (|| {
            if !self.write_byte(addr << 1)? {
                return Err(Error::Nack);
            }
            for &b in bytes {
                if !self.write_byte(b)? {
                    return Err(Error::Nack);
                }
            }
            Ok(())
        })();
        self.finish(r)
    }

    /// Write `reg`, then read `buf.len()` bytes (repeated START).
    pub fn read_reg(&mut self, addr: u8, reg: u8, buf: &mut [u8]) -> Result<(), Error> {
        self.start()?;
        let r = (|| {
            if !self.write_byte(addr << 1)? || !self.write_byte(reg)? {
                return Err(Error::Nack);
            }
            self.start()?;
            if !self.write_byte((addr << 1) | 1)? {
                return Err(Error::Nack);
            }
            let n = buf.len();
            for (i, b) in buf.iter_mut().enumerate() {
                *b = self.read_byte(i + 1 < n)?;
            }
            Ok(())
        })();
        self.finish(r)
    }
}

/// A simulated register-file target on simulated open-drain wires, for tests.
#[cfg(test)]
pub mod sim {
    use super::Lines;

    pub struct Sim {
        pub addr: u8,
        pub regs: [u8; 256],
        pub present: bool,
        // wire state as driven by the controller
        sda_c: bool,
        scl_c: bool,
        // target state machine
        target_sda_low: bool,
        bits: u8,
        nbits: u8,
        phase: Phase,
        reg: u8,
        reading: bool,
        first: bool,
        out: u8,
    }

    #[derive(Clone, Copy, PartialEq, Debug)]
    enum Phase {
        Idle,
        Addr,
        AckAddr,
        Data,
        AckData,
        Send,
        GetAck,
        Ignore,
    }

    impl Sim {
        pub fn new(addr: u8) -> Self {
            Self {
                addr,
                regs: [0; 256],
                present: true,
                sda_c: true,
                scl_c: true,
                target_sda_low: false,
                bits: 0,
                nbits: 0,
                phase: Phase::Idle,
                reg: 0,
                reading: false,
                first: true,
                out: 0,
            }
        }

        fn line_sda(&self) -> bool {
            self.sda_c && !self.target_sda_low
        }
    }

    impl Lines for Sim {
        fn set_sda(&mut self, high: bool) {
            let before = self.line_sda();
            self.sda_c = high;
            let after = self.line_sda();
            if self.scl_c && before && !after {
                // START (or repeated START)
                self.phase = Phase::Addr;
                self.bits = 0;
                self.nbits = 0;
                self.target_sda_low = false;
            } else if self.scl_c && !before && after {
                self.phase = Phase::Idle; // STOP
                self.target_sda_low = false;
            }
        }

        fn set_scl(&mut self, high: bool) {
            let rising = !self.scl_c && high;
            let falling = self.scl_c && !high;
            self.scl_c = high;
            if rising {
                match self.phase {
                    Phase::Addr | Phase::Data => {
                        self.bits = (self.bits << 1) | self.line_sda() as u8;
                        self.nbits += 1;
                    }
                    Phase::GetAck => {
                        if self.line_sda() {
                            self.phase = Phase::Ignore; // controller NACKed: done
                        }
                    }
                    _ => {}
                }
            }
            if falling {
                match self.phase {
                    Phase::Addr if self.nbits == 8 => {
                        if self.present && self.bits >> 1 == self.addr {
                            self.reading = self.bits & 1 == 1;
                            self.target_sda_low = true;
                            self.phase = Phase::AckAddr;
                        } else {
                            self.phase = Phase::Ignore;
                        }
                    }
                    Phase::Data if self.nbits == 8 => {
                        if self.first {
                            self.reg = self.bits;
                            self.first = false;
                        } else {
                            self.regs[self.reg as usize] = self.bits;
                            self.reg = self.reg.wrapping_add(1);
                        }
                        self.target_sda_low = true;
                        self.phase = Phase::AckData;
                    }
                    Phase::AckAddr => {
                        self.target_sda_low = false;
                        if self.reading {
                            self.out = self.regs[self.reg as usize];
                            self.reg = self.reg.wrapping_add(1);
                            self.nbits = 0;
                            self.target_sda_low = self.out & 0x80 == 0;
                            self.phase = Phase::Send;
                        } else {
                            self.first = true;
                            self.bits = 0;
                            self.nbits = 0;
                            self.phase = Phase::Data;
                        }
                    }
                    Phase::AckData => {
                        self.target_sda_low = false;
                        self.bits = 0;
                        self.nbits = 0;
                        self.phase = Phase::Data;
                    }
                    Phase::Send => {
                        self.nbits += 1;
                        if self.nbits == 8 {
                            self.target_sda_low = false;
                            self.phase = Phase::GetAck;
                        } else {
                            self.target_sda_low = (self.out << self.nbits) & 0x80 == 0;
                        }
                    }
                    Phase::GetAck => {
                        self.out = self.regs[self.reg as usize];
                        self.reg = self.reg.wrapping_add(1);
                        self.nbits = 0;
                        self.target_sda_low = self.out & 0x80 == 0;
                        self.phase = Phase::Send;
                    }
                    _ => {}
                }
            }
        }

        fn sda(&mut self) -> bool {
            self.line_sda()
        }
        fn scl(&mut self) -> bool {
            self.scl_c
        }
        fn delay(&mut self) {}
    }
}

#[cfg(test)]
mod tests {
    use super::sim::Sim;
    use super::*;

    #[test]
    fn writes_registers() {
        let mut bus = BitBang::new(Sim::new(0x28));
        bus.write(0x28, &[0x1F, 0x2F, 0x30]).unwrap();
        assert_eq!(bus.lines().regs[0x1F], 0x2F);
        assert_eq!(bus.lines().regs[0x20], 0x30);
    }

    #[test]
    fn reads_registers() {
        let mut s = Sim::new(0x28);
        s.regs[0xFD] = 0x67;
        s.regs[0xFE] = 0x5D;
        let mut bus = BitBang::new(s);
        let mut b = [0u8; 2];
        bus.read_reg(0x28, 0xFD, &mut b).unwrap();
        assert_eq!(b, [0x67, 0x5D]);
    }

    #[test]
    fn missing_device_is_a_nack_and_bus_is_left_idle() {
        let mut bus = BitBang::new(Sim::new(0x28));
        assert_eq!(bus.write(0x29, &[1]), Err(Error::Nack));
        let mut b = [0u8; 1];
        assert_eq!(bus.read_reg(0x30, 0, &mut b), Err(Error::Nack));
        assert!(bus.lines().sda() && bus.lines().scl());
        // and it still works afterwards
        bus.write(0x28, &[0x05, 0xAA]).unwrap();
        assert_eq!(bus.lines().regs[5], 0xAA);
    }

    #[test]
    fn recover_on_idle_bus_is_fine() {
        let mut bus = BitBang::new(Sim::new(0x28));
        assert_eq!(bus.recover(), Ok(()));
    }
}
