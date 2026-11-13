"""Read old Node password hashes; Django upgrades them on successful login."""
import hashlib
import hmac
import re
from django.contrib.auth.hashers import BasePasswordHasher, mask_hash


class LegacyScryptPasswordHasher(BasePasswordHasher):
    algorithm = 'legacy_scrypt'

    def encode(self, password, salt):
        key = hashlib.scrypt(password.encode('utf-8'), salt=salt.encode('utf-8'), n=32768, r=8, p=3, dklen=64, maxmem=64 * 1024 * 1024)
        return f'{self.algorithm}$32768$8$3${salt}${key.hex()}'

    def verify(self, password, encoded):
        if not re.fullmatch(r'legacy_scrypt\$32768\$8\$3\$[0-9a-f]{32}\$[0-9a-f]{128}', encoded):
            return False
        return hmac.compare_digest(self.encode(password, encoded.split('$')[4]), encoded)

    def safe_summary(self, encoded):
        return {'algorithm': self.algorithm, 'hash': mask_hash(encoded.split('$')[-1])}

    def must_update(self, encoded):
        return True
