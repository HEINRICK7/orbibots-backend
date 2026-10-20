import hashlib
import unittest

from app.src.infra.adapters.authentication.invitation_tokens import (
    SecureInvitationTokenIssuer,
)


class SecureInvitationTokenIssuerTests(unittest.TestCase):
    def test_issues_url_safe_random_token_and_persists_only_its_sha256_hash(self) -> None:
        issuer = SecureInvitationTokenIssuer()

        first = issuer.issue()
        second = issuer.issue()

        self.assertNotEqual(first.raw_token, second.raw_token)
        self.assertTrue(first.raw_token.replace("-", "").replace("_", "").isalnum())
        self.assertEqual(
            hashlib.sha256(first.raw_token.encode("utf-8")).hexdigest(),
            first.token_hash,
        )
        self.assertNotEqual(first.raw_token, first.token_hash)
        self.assertEqual(64, len(first.token_hash))
        self.assertNotIn(first.raw_token, repr(first))


if __name__ == "__main__":
    unittest.main()
