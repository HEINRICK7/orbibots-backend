import logging
import os
import unittest
from unittest.mock import patch

from app.src.infra.setup.logging_config import configure_logging


class LoggingConfigTests(unittest.TestCase):
    def tearDown(self) -> None:
        configure_logging.cache_clear()
        configure_logging()

    def test_log_level_is_configurable_from_environment(self) -> None:
        configure_logging.cache_clear()
        with patch.dict(os.environ, {"LOG_LEVEL": "DEBUG"}):
            configure_logging()

        root_logger = logging.getLogger()
        self.assertEqual(root_logger.level, logging.DEBUG)
        self.assertTrue(
            all(handler.level == logging.DEBUG for handler in root_logger.handlers)
        )

    def test_unknown_log_level_is_rejected(self) -> None:
        configure_logging.cache_clear()
        with patch.dict(os.environ, {"LOG_LEVEL": "NOPE"}):
            with self.assertRaisesRegex(ValueError, "Unsupported LOG_LEVEL"):
                configure_logging()


if __name__ == "__main__":
    unittest.main()
