from collections import defaultdict
import unittest
from unittest.mock import Mock

import discord

import statbot.sql

class TestSql(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        addr = 'postgresql://statbot_test@/statbot_test'
        cache_sizes = defaultdict(int)
        cls.sql = statbot.sql.DiscordSqlHandler(addr, cache_sizes)

    def setUp(self):
        self.transaction = self.sql.conn.begin()

    def tearDown(self):
        self.transaction.rollback()

    @classmethod
    def tearDownClass(cls):
        cls.sql.conn.close()

    def test_upsert_guild(self):
        user = Mock()
        guild = Mock()
        user.configure_mock(id=0, name='cow', discriminator=1, avatar=None, bot=False)
        guild.configure_mock(id=1, owner=user, name='statbot_test', icon='',
                region=discord.VoiceRegion.us_south,
                afk_channel=None, afk_timeout=2, mfa_level=False,
                verification_level=discord.VerificationLevel.none,
                explicit_content_filter=discord.ContentFilter.disabled, features=[], splash=None)
        with self.sql.transaction() as trans:
            self.sql.add_user(trans, user)
            self.sql.upsert_guild(trans, guild)
