//! Host tests: the driver against a simulated I2C bus that plays back what a Nunchuk would answer.
use embedded_hal::delay::DelayNs;
use embedded_hal::i2c::{ErrorKind, ErrorType, I2c, NoAcknowledgeSource, Operation};
use nunchuck_driver::*;

#[derive(Debug, Clone, Copy, PartialEq)]
struct BusError;
impl embedded_hal::i2c::Error for BusError {
    fn kind(&self) -> ErrorKind {
        ErrorKind::NoAcknowledge(NoAcknowledgeSource::Address)
    }
}

/// Records every write; answers every read with the next scripted 6 bytes. `present = false` acts as an empty socket.
#[derive(Default)]
struct FakeBus {
    present: bool,
    writes: Vec<(u8, Vec<u8>)>,
    reads: Vec<[u8; 6]>,
    read_addrs: Vec<u8>,
}

impl ErrorType for FakeBus {
    type Error = BusError;
}

impl I2c for FakeBus {
    fn transaction(&mut self, address: u8, ops: &mut [Operation<'_>]) -> Result<(), BusError> {
        if !self.present {
            return Err(BusError);
        }
        for op in ops {
            match op {
                Operation::Write(b) => self.writes.push((address, b.to_vec())),
                Operation::Read(buf) => {
                    self.read_addrs.push(address);
                    let next = self.reads.remove(0);
                    buf.copy_from_slice(&next[..buf.len()]);
                }
            }
        }
        Ok(())
    }
}

#[derive(Default)]
struct FakeDelay {
    total_ns: u64,
}
impl DelayNs for FakeDelay {
    fn delay_ns(&mut self, ns: u32) {
        self.total_ns += u64::from(ns);
    }
}

fn bus_with(reads: &[[u8; 6]]) -> FakeBus {
    FakeBus { present: true, reads: reads.to_vec(), ..Default::default() }
}

#[test]
fn address_is_the_wii_extension_address() {
    assert_eq!(ADDRESS, 0x52);
}

#[test]
fn init_sends_the_plain_mode_wake_up() {
    let mut n = Nunchuk::new(bus_with(&[]));
    let mut d = FakeDelay::default();
    n.init(&mut d).unwrap();
    let bus = n.release();
    assert_eq!(bus.writes, vec![(0x52, vec![0xF0, 0x55]), (0x52, vec![0xFB, 0x00])]);
    assert!(d.total_ns >= 2 * u64::from(INIT_STEP_DELAY_US) * 1000);
}

#[test]
fn read_asks_for_register_0_then_waits_then_reads() {
    let mut n = Nunchuk::new(bus_with(&[[128, 128, 128, 128, 128, 0xFF]]));
    let mut d = FakeDelay::default();
    n.read(&mut d).unwrap();
    assert!(d.total_ns >= u64::from(CONVERSION_DELAY_US) * 1000);
    let bus = n.release();
    assert_eq!(bus.writes, vec![(0x52, vec![0x00])]);
    assert_eq!(bus.read_addrs, vec![0x52]);
}

#[test]
fn decodes_stick_accelerometer_and_buttons() {
    // stick 0x10 / 0xF0; accel tops 0x80 0x40 0xC0; byte 5: Z low bits 11, Y 10, X 01, C up (1), Z down (0)
    let r = Reading::decode(&[0x10, 0xF0, 0x80, 0x40, 0xC0, 0b11_10_01_10]).unwrap();
    assert_eq!((r.joy_x, r.joy_y), (0x10, 0xF0));
    assert_eq!(r.accel_x, (0x80 << 2) | 0b01);
    assert_eq!(r.accel_y, (0x40 << 2) | 0b10);
    assert_eq!(r.accel_z, (0xC0 << 2) | 0b11);
    assert!(r.z);
    assert!(!r.c);
}

#[test]
fn buttons_are_active_low() {
    let none = Reading::decode(&[0, 0, 0, 0, 0, 0b11]).unwrap();
    assert!(!none.c && !none.z);
    let both = Reading::decode(&[0, 0, 0, 0, 0, 0b00]).unwrap();
    assert!(both.c && both.z);
    let c_only = Reading::decode(&[0, 0, 0, 0, 0, 0b01]).unwrap();
    assert!(c_only.c && !c_only.z);
}

#[test]
fn accelerometer_covers_ten_bits() {
    let max = Reading::decode(&[0, 0, 0xFF, 0xFF, 0xFF, 0xFC]).unwrap();
    assert_eq!((max.accel_x, max.accel_y, max.accel_z), (1023, 1023, 1023));
    let min = Reading::decode(&[0, 0, 0, 0, 0, 0x03]).unwrap();
    assert_eq!((min.accel_x, min.accel_y, min.accel_z), (0, 0, 0));
    assert_eq!(max.accel_signed(), (511, 511, 511));
    assert_eq!(min.accel_signed(), (-512, -512, -512));
}

#[test]
fn all_ff_means_not_initialised() {
    assert_eq!(Reading::decode(&[0xFF; 6]), None);
    let mut n = Nunchuk::new(bus_with(&[[0xFF; 6]]));
    assert_eq!(n.read(&mut FakeDelay::default()), Err(Error::NotReady));
}

#[test]
fn empty_socket_is_a_bus_error() {
    let mut n = Nunchuk::new(FakeBus::default());
    assert_eq!(n.init(&mut FakeDelay::default()), Err(Error::Bus(BusError)));
    assert_eq!(n.read(&mut FakeDelay::default()), Err(Error::Bus(BusError)));
}

#[test]
fn identify_accepts_a_nunchuk() {
    let mut n = Nunchuk::new(bus_with(&[NUNCHUK_ID]));
    assert_eq!(n.identify(&mut FakeDelay::default()), Ok(NUNCHUK_ID));
    assert_eq!(n.release().writes, vec![(0x52, vec![0xFA])]);
}

#[test]
fn identify_rejects_other_controllers() {
    let classic = [0x00, 0x00, 0xA4, 0x20, 0x01, 0x01];
    let mut n = Nunchuk::new(bus_with(&[classic]));
    assert_eq!(n.identify(&mut FakeDelay::default()), Err(Error::NotANunchuk(classic)));
    let mut n = Nunchuk::new(bus_with(&[[0xFF; 6]]));
    assert_eq!(n.identify(&mut FakeDelay::default()), Err(Error::NotReady));
}

fn stick_at(x: u8, y: u8) -> Reading {
    Reading { joy_x: x, joy_y: y, ..Default::default() }
}

#[test]
fn stick_dead_band_and_range() {
    let s = Stick::default();
    assert_eq!(s.position(&stick_at(128, 128)), (0, 0));
    assert_eq!(s.position(&stick_at(140, 116)), (0, 0)); // inside the 16-step band
    assert_eq!(s.position(&stick_at(145, 111)), (1, -1)); // just outside: starts from 0, no jump
    assert_eq!(s.position(&stick_at(255, 0)), (111, -112));
}

#[test]
fn stick_calibration_moves_the_centre() {
    let mut s = Stick::default();
    s.calibrate(&stick_at(120, 135));
    assert_eq!(s.position(&stick_at(120, 135)), (0, 0));
    assert_eq!(s.position(&stick_at(128, 128)), (0, 0));
    assert_eq!(s.position(&stick_at(140, 135)), (4, 0));
}

#[test]
fn stick_directions() {
    let s = Stick::default();
    assert_eq!(s.direction(&stick_at(128, 128)), None);
    assert_eq!(s.direction(&stick_at(250, 140)), Some(Direction::Right));
    assert_eq!(s.direction(&stick_at(5, 128)), Some(Direction::Left));
    assert_eq!(s.direction(&stick_at(130, 250)), Some(Direction::Up));
    assert_eq!(s.direction(&stick_at(128, 3)), Some(Direction::Down));
    assert_eq!(s.direction(&stick_at(200, 200)), Some(Direction::Right)); // diagonal: left/right wins
}

#[test]
fn button_events() {
    let up = Reading::default();
    let c_down = Reading { c: true, ..Default::default() };
    let both = Reading { c: true, z: true, ..Default::default() };
    let e = Buttons::between(&up, &c_down);
    assert!(e.c_pressed && !e.z_pressed && e.any());
    let e = Buttons::between(&c_down, &both);
    assert!(e.z_pressed && !e.c_pressed);
    let e = Buttons::between(&both, &up);
    assert!(e.c_released && e.z_released);
    assert!(!Buttons::between(&both, &both).any());
}

#[test]
fn a_badge_loop_end_to_end() {
    // what a badge does: init, identify, then poll; the maker's demo prints Z, stick Y and accel X the same way
    let reports = [NUNCHUK_ID, [128, 128, 128, 128, 128, 0xFF], [128, 250, 0x90, 128, 128, 0xFE]];
    let mut n = Nunchuk::new(bus_with(&reports));
    let mut d = FakeDelay::default();
    n.init(&mut d).unwrap();
    n.identify(&mut d).unwrap();
    let first = n.read(&mut d).unwrap();
    let mut stick = Stick::default();
    stick.calibrate(&first);
    let second = n.read(&mut d).unwrap();
    assert!(Buttons::between(&first, &second).z_pressed);
    assert_eq!(stick.direction(&second), Some(Direction::Up));
    assert_eq!(second.accel_x, (0x90 << 2) | 0b11);
}
