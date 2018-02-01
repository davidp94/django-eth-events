# -*- coding: utf-8 -*-
from __future__ import unicode_literals
from json import loads
from web3 import TestRPCProvider
from eth_utils import to_normalized_address
from django_eth_events.utils import remove_0x_head
from django.test import TestCase
from django_eth_events.factories import DaemonFactory
from django_eth_events.event_listener import EventListener
from django_eth_events.utils import remove_0x_head
from django_eth_events.tests.codes import abi, bin_hex
from web3 import TestRPCProvider


class TestDaemon(TestCase):
    def setUp(self):
        self.rpc = TestRPCProvider()
        self.daemon = DaemonFactory()
        self.bot = EventListener(self.rpc)
        self.bot.decoder.methods = {}
        self.maxDiff = None

    def tearDown(self):
        self.rpc.server.shutdown()
        self.rpc.server.server_close()
        self.rpc = None

    def test_next_block(self):
        self.assertListEqual(list(self.bot.get_last_mined_blocks()), [])
        factory = self.bot.web3.eth.contract(abi, bytecode=bin_hex)
        tx_hash = factory.deploy()
        self.bot.web3.eth.getTransactionReceipt(tx_hash)
        tx_hash2 = factory.deploy()
        self.bot.web3.eth.getTransactionReceipt(tx_hash2)
        self.assertEquals(list(self.bot.get_last_mined_blocks()), [1])
        self.bot.update_block_number(1)
        self.assertEquals(list(self.bot.get_last_mined_blocks()), [])

    def test_load_abis(self):
        self.assertIsNotNone(self.bot.decoder)
        self.assertEquals(len(self.bot.decoder.methods), 0)
        self.assertEquals(self.bot.decoder.add_abi([]), 0)
        self.assertEquals(len(self.bot.decoder.methods), 0)
        # No ABIs
        self.assertEquals(self.bot.decoder.add_abi(abi), 6)
        self.assertEquals(len(self.bot.decoder.methods), 6)
        self.assertEquals(self.bot.decoder.add_abi([{'nothing': 'wrong'}]), 0)

        self.assertEquals(self.bot.decoder.add_abi(abi), 6)
        self.assertEquals(self.bot.decoder.add_abi([{'nothing': 'wrong'}]), 0)

    def test_get_logs(self):
        # no logs before transactions
        logs, block_info = self.bot.get_logs(0)
        self.assertListEqual([], logs)

        # create Wallet Factory contract
        factory = self.bot.web3.eth.contract(abi, bytecode=bin_hex)
        self.assertIsNotNone(factory)
        tx_hash = factory.deploy()
        self.assertIsNotNone(tx_hash)
        receipt = self.bot.web3.eth.getTransactionReceipt(tx_hash)
        self.assertIsNotNone(receipt)
        self.assertIsNotNone(receipt.get('contractAddress'))
        factory_address = receipt[u'contractAddress']

        logs, block_info = self.bot.get_logs(0)
        self.assertListEqual([], logs)

        # send deploy function, will trigger two events
        self.bot.decoder.add_abi(abi)
        factory_instance = self.bot.web3.eth.contract(abi, factory_address)
        owners = self.bot.web3.eth.accounts[0:2]
        required_confirmations = 1
        daily_limit = 0
        tx_hash = factory_instance.transact().create(owners, required_confirmations, daily_limit)
        receipt = self.bot.web3.eth.getTransactionReceipt(tx_hash)
        self.assertIsNotNone(receipt)
        self.assertListEqual(list(self.bot.get_last_mined_blocks()), [1])
        self.bot.update_block_number(1)
        self.assertListEqual(list(self.bot.get_last_mined_blocks()), [])
        logs, block_info = self.bot.get_logs(1)
        self.assertEqual(2, len(logs))
        decoded = self.bot.decoder.decode_logs(logs)
        self.assertEqual(2, len(decoded))
        self.assertDictEqual(
            {
                u'address': remove_0x_head(factory_address),
                u'name': u'OwnersInit',
                u'params': [
                    {
                        u'name': u'owners',
                        u'value': [remove_0x_head(to_normalized_address(account))
                                   for account
                                   in self.bot.web3.eth.accounts[0:2]]
                    }
                ]
            },
            decoded[0]
        )
        self.assertDictEqual(
            {
                u'address': remove_0x_head(factory_address),
                u'name': u'ContractInstantiation',
                u'params': [
                    {
                        u'name': 'sender',
                        u'value': remove_0x_head(to_normalized_address(self.bot.web3.eth.coinbase))
                    },
                    {
                        u'name': 'instantiation',
                        u'value': remove_0x_head(decoded[1][u'params'][1][u'value'])
                    }
                ]
            },
            decoded[1]
        )
