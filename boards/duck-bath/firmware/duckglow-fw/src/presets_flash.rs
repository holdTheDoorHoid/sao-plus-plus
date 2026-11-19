//! The power-on presets in flash: one 4 KB sector at the very end of the
//! module's flash, far past the firmware (which is about 100 KB). Written only
//! when the badge writes 42 to the save register and the settings changed.

use duckglow_core::presets::BLOB_LEN;
use esp_hal::peripherals::FLASH;
use esp_storage::FlashStorage;

pub struct Presets<'d> {
    flash: FlashStorage<'d>,
    at: u32,
}

impl<'d> Presets<'d> {
    pub fn new(flash: FLASH<'d>) -> Self {
        let f = FlashStorage::new(flash);
        #[cfg(feature = "esp32s3")]
        let f = f.multicore_auto_park();
        let at = f.capacity() as u32 - FlashStorage::SECTOR_SIZE;
        Self { flash: f, at }
    }

    /// Read the stored bytes; false if the flash could not be read.
    pub fn load(&mut self, out: &mut [u8; BLOB_LEN]) -> bool {
        self.flash.read(self.at, out).is_ok()
    }

    /// Erase the sector and write the blob. True if it reads back the same.
    pub fn save(&mut self, blob: &[u8; BLOB_LEN]) -> bool {
        if self.flash.erase(self.at, self.at + FlashStorage::SECTOR_SIZE).is_err() {
            return false;
        }
        if self.flash.write_nor(self.at, blob).is_err() {
            return false;
        }
        let mut back = [0u8; BLOB_LEN];
        self.flash.read(self.at, &mut back).is_ok() && back == *blob
    }

    /// Factory reset: forget the presets.
    pub fn erase(&mut self) {
        let _ = self.flash.erase(self.at, self.at + FlashStorage::SECTOR_SIZE);
    }
}
