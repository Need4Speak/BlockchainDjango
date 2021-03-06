#!/usr/bin/python3
# -*- coding: UTF-8 -*-

import logging
import time
import hashlib

from ecdsa import VerifyingKey

from ..util import couchdb_util
from ..util.const import Const
from ..util.signature import Signature
from ..entity.transaction import Transaction
from ..entity.patient import Patient
from ..entity.doctor import Doctor
from ..entity.medical_record import MedicalRecord
from ..entity.patient_record import PatientRecord
from ..entity.patient_last_record import PatientLastRecord
from ..entity.doctor_record import DoctorRecord
from ..entity.doctor_last_record import DoctorLastRecord
from ..entity.medical_record_del import MedicalRecordDel
from ..entity.medical_record_update import MedicalRecordUpdate

db = couchdb_util.get_db(Const.DB_NAME)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class TransactionService(object):

    @staticmethod
    def gen_tx(content):
        """
        测试生成一条transaction
        :return: 生成的transaction
        """
        if content is None:
            raise Exception("The content is None!")

        pvt_key, pub_key = Signature.get_key_pair()

        timestamp = str(time.time())
        pub_key_str = bytes.hex(pub_key.to_string())
        # 若content是对象类型，则将其转化为json格式字符串存储
        if isinstance(content, str):
            temp_tx = Transaction(pub_key_str, content, timestamp)
            signature = Signature.sign(pvt_key, content)
        else:
            temp_tx = Transaction(pub_key_str, content.__dict__, timestamp)
            signature = Signature.sign(pvt_key, content.__dict__.__str__())

        temp_tx.signature = bytes.hex(signature)
        temp_tx.id = Signature.gen_id_by_sig(temp_tx.signature)
        temp_tx.tx_type = TransactionService.get_tx_type(content)
        return temp_tx

    @staticmethod
    def get_tx_type(content):
        """
        判断 content 类型并返回
        :param content: Transaction 对象所存储的内容
        :return: content 类型
        """
        if isinstance(content, Patient):
            logger.info("此 Transaction 存储的类型为 patient")
            return 'patient'

        elif isinstance(content, Doctor):
            logger.info("此 Transaction 存储的类型为 doctor")
            return 'doctor'

        elif isinstance(content, MedicalRecord):
            logger.info("此 Transaction 存储的类型为 medical_record")
            return 'medical_record'

        elif isinstance(content, PatientRecord):
            logger.info("此 Transaction 存储的类型为 patient_record")
            return 'patient_record'

        elif isinstance(content, PatientLastRecord):
            logger.info("此 Transaction 存储的类型为 patient_last_record")
            return 'patient_last_record'

        elif isinstance(content, DoctorRecord):
            logger.info("此 Transaction 存储的类型为 doctor_record")
            return 'doctor_record'

        elif isinstance(content, DoctorLastRecord):
            logger.info("此 Transaction 存储的类型为 doctor_last_record")
            return 'doctor_last_record'

        elif isinstance(content, MedicalRecordDel):
            logger.info("此 Transaction 存储的类型为 medical_record_del")
            return 'medical_record_del'

        elif isinstance(content, MedicalRecordUpdate):
            logger.info("此 Transaction 存储的类型为 medical_record_update")
            return 'medical_record_update'

        elif isinstance(content, str):
            logger.info("此 Transaction 存储的类型为 string")
            return 'string'

        elif content is None:
            logger.info("此 Transaction 存储的类型为 none")
            return 'none'

        else:
            raise Exception('未知 Transaction 类型！')

    @staticmethod
    def save_tx(transaction):
        """ 将一条 transaction 信息存储 couchdb数据库里"""
        if not isinstance(transaction, Transaction):
            raise Exception("形参transaction类型错误，必须为Transaction类的实例！")
        else:
            couchdb_util.save(db, {'_id': transaction.id, 'Transaction': transaction.__dict__})

    @staticmethod
    def save_tx_list(transaction_list):
        """ 循环调用 save_tx, 将transaction list 存入到数据库中"""
        for each_tx in transaction_list:
            TransactionService.save_tx(each_tx)

    @staticmethod
    def get_tx_ids(transaction_list):
        """根据传入的 transaction_list，得到各个 transaction 的 id，以tuple的形式返回"""
        id_list = []
        for each_transaction in transaction_list:
            id_list.append(each_transaction.id)
        return tuple(id_list)

    @staticmethod
    def find_tx_by_id(tx_id):
        """
        根据Transaction的id获取存储的数据库里的Transaction的信息，以dict的形式返回
        :param tx_id:
        :return:
        """
        # db = couchdb_util.get_db(Const.DB_NAME)
        tx_doc = db[tx_id]
        transaction_dict = tx_doc['Transaction']
        transaction_dict['tx_id'] = tx_id
        return transaction_dict

    @staticmethod
    def find_txs_by_ids(tx_id_list):
        """
        根据tx_id_list)中所存储的所有tx的id查找相应的Transaction，并以list的形式返回
        :param tx_id_list:
        :return:
        """
        tx_dicts = []
        for tx_id in tx_id_list:
            tx_dicts.append(TransactionService.find_tx_by_id(tx_id))

        return tx_dicts

    @staticmethod
    def find_contents_by_id(tx_id):
        """
        根据tx_id_list)中所存储的所有tx的id查找相应的Transaction中的content内容，并以list的形式返回
        :param tx_id:
        :return:
        """
        tx_dict = TransactionService.find_tx_by_id(tx_id)
        tx_content_dict = tx_dict['content']
        # 将该医疗记录的tx_id和timestamp存入到所返回的dict中
        tx_content_dict['in_tx_id'] = tx_dict['tx_id']
        tx_content_dict['timestamp'] = tx_dict['timestamp']

        return tx_content_dict

    @staticmethod
    def find_contents_by_ids(tx_id_list):
        """
        根据tx_id_list)中所存储的所有tx的id查找相应的Transaction中的content内容，并以list的形式返回
        :param tx_id_list:
        :return:
        """
        tx_dicts = TransactionService.find_txs_by_ids(tx_id_list)
        content_dicts = []
        for tx_dict in tx_dicts:
            tx_content_dict = tx_dict['content']
            # 将该医疗记录的tx_id和timestamp存入到所返回的dict中
            tx_content_dict['in_tx_id'] = tx_dict['tx_id']
            tx_content_dict['timestamp'] = tx_dict['timestamp']
            content_dicts.append(tx_content_dict)

        return content_dicts

    @staticmethod
    def verify_tx(tx):
        """
        判断 tx 的签名是否正确
        :param tx: Transaction 对象
        :return:
        """
        sig_str = tx.signature
        pub_key_str = tx.pub_key
        content_str = tx.content

        vk = VerifyingKey.from_string(bytes.fromhex(pub_key_str), curve=Const.CURVE)
        # transaction.content 作为签名的内容
        return vk.verify(bytes.fromhex(sig_str), content_str.encode('utf-8'))
