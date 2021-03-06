#!/usr/bin/python3
# -*- coding: UTF-8 -*-
import logging
import time

from ..entity.medical_record import MedicalRecord
from ..entity.patient_record import PatientRecord
from ..entity.doctor_record import DoctorRecord
from ..entity.medical_record_del import MedicalRecordDel
from ..entity.medical_record_update import MedicalRecordUpdate

from ..util.const import RecordType, FindRecordType
from ..util import couchdb_util
from ..util.const import Const
from .transaction_service import TransactionService
from .block_service import BlockService
from .block_chain_service import BlockChainService

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class MedicalRecordService(object):
    
    @staticmethod
    def add(patient_id, doctor_id, record_loc, chief_complaint, present_illness_history, past_history):
        """
        根据传入的参数构建一个就诊记录对象，存入区块链中，并返回该区块
        :param patient_id:
        :param doctor_id:
        :param record_loc:
        :param chief_complaint:
        :param present_illness_history:
        :param past_history:
        :param rtn_tx_id:是否返回医疗记录的id
        :return:
        """
        record_time = time.strftime("%Y%m%d%H%M%S", time.localtime())
        record_id = patient_id + record_time
        record_type = RecordType.ADD.value
        medical_record = MedicalRecord(record_id, doctor_id, patient_id, record_time, record_loc,
                                       chief_complaint, present_illness_history, past_history, record_type)

        # 添加一条就诊记录信息时，同时添加病人与该就诊记录对照关系的Transaction和添加医生与该就诊记录对照关系的Transaction
        record_tx = TransactionService.gen_tx(medical_record)
        patient_record_tx = MedicalRecordService.gen_medical_patient_tx(patient_id, record_tx.id)
        doctor_record_tx = MedicalRecordService.gen_medical_doctor_tx(doctor_id, record_tx.id)

        last_block_id = BlockService.add_block([record_tx, patient_record_tx, doctor_record_tx])

        return last_block_id

    @staticmethod
    def find_by_id(record_id):
        """
        根据就诊记录的ID返回就诊记录的内容，以dict的形式。
        若不存在，则返回None
        :param record_id:
        :return:
        """
        tx_type = 'medical_record'
        return BlockChainService.find_content(record_id, tx_type)

    @staticmethod
    def gen_medical_patient_tx(patient_id, record_tx_id):
        """
        用于生成 就诊记录与病人对照关系的函数
        :param patient_id:
        :param record_tx_id:
        :return:
        """
        patient_record = PatientRecord(patient_id, record_tx_id)
        patient_record_tx = TransactionService.gen_tx(patient_record)
        return patient_record_tx

    @staticmethod
    def gen_medical_doctor_tx(doctor_id, record_tx_id):
        """
        用于生成 就诊记录与医生对照关系的函数
        :param doctor_id:
        :param record_tx_id:
        :return:
        """
        doctor_record = DoctorRecord(doctor_id, record_tx_id)
        doctor_record_tx = TransactionService.gen_tx(doctor_record)
        return doctor_record_tx

    @staticmethod
    def find_by_relation(tx_type, identifier, id_name, find_record_type=FindRecordType.NORMAL.value):
        """
        根据 tx_type, identifier, id_name 来查找对应 transaction 的 id，存入list中并返回
        :param tx_type:
        :param identifier: 如patient_id, doctor_id
        :param id_name: 如'patient_id', 'doctor_id'
        :param find_record_type: 默认不去除被删除的记录
        :return:
        """
        record_list = []

        deleted_record_list = []
        deleted_record_tx_id_list = []

        updated_old_record_list = []
        updated_record_tx_id_list = []

        db = couchdb_util.get_db(Const.DB_NAME)
        doc = db[Const.LAST_BLOCK_ID]
        last_block = doc['last_block_id']
        doc = db[last_block]

        while True:
            # 若当前区块的 pre_id 为0，则表示便利整个区块链后，均未找到 id 为 所查询 id 的病人返回 none
            # 创世区块不存储transaction， 跳过
            if '0000000000000000000000000000000000000000000000000000000000000000' == doc['pre_id']:
                break

            tx_list = doc['tx_list']
            # tx 保存了 一个Transaction 的 ID
            for tx in tx_list:
                tx_doc = db[tx]
                transaction_dict = tx_doc['Transaction']

                # 若只检索被删除的就诊记录时，则不检索其他就诊记录。否则的话，则检索
                if find_record_type != FindRecordType.DELETED.value and tx_type == transaction_dict['tx_type']:
                    content_dict = transaction_dict['content']
                    if identifier == content_dict[id_name]:
                        logger.info('Find ' + identifier + ', in transaction ' +
                                    transaction_dict['id'] + ', in block ' + doc['_id'])
                        record_list.append(content_dict['record_tx_id'])

                # 检查 find_record_type 的值，判断是否检索被删除的就诊记录
                # 就诊记录的tx_id
                if (find_record_type == FindRecordType.NORMAL.value
                    or find_record_type == FindRecordType.DELETED.value) \
                        and 'medical_record_del' == transaction_dict['tx_type']:
                    del_record_dict = transaction_dict['content']

                    # 如果传入的 id 与 medical_record_del 中记录的，对应id_name的id相同时，
                    # 则将该 medical_record_del 中记录的 tx_id 加入到 deleted_record_list 中
                    if identifier == del_record_dict[id_name]:
                        deleted_record_list.append(del_record_dict['tx_id'])
                        deleted_record_tx_id_list.append(tx_doc['_id'])  # tx_doc['_id'] 的内容为当前交易单的id

                # 检查 find_record_type 的值，判断是否检索 就诊记录更新关系 的就诊记录
                # 就诊记录的tx_id
                if (find_record_type == FindRecordType.NORMAL.value
                    or find_record_type == FindRecordType.UPDATED.value) \
                        and 'medical_record_update' == transaction_dict['tx_type']:
                    update_record_dict = transaction_dict['content']

                    # 如果传入的 id 与 medical_record_update 中记录的，对应id_name的id相同时，
                    # 则将该 medical_record_update 中记录的 tx_id 加入到 update_record_list 中
                    if identifier == update_record_dict['old_' + id_name]:
                        updated_old_record_list.append(update_record_dict['old_tx_id'])
                        updated_record_tx_id_list.append(tx_doc['_id'])  # tx_doc['_id'] 的内容为当前交易单的id

                logger.info(str(transaction_dict))

            doc = db[doc['pre_id']]

        logger.info('deleted_record_list: ' + str(deleted_record_list))
        logger.info('record_list: ' + str(record_list))

        if find_record_type == FindRecordType.NORMAL.value:
            # 从 record_list 中去除已被删除的元素
            for deleted_record in deleted_record_list:
                record_list.remove(deleted_record)

            # 从 record_list 中去除已被更新过的旧的就诊记录
            for updated_old_record in updated_old_record_list:
                record_list.remove(updated_old_record)

        if find_record_type == FindRecordType.NORMAL.value or find_record_type == FindRecordType.ALL.value:
            return record_list

        elif find_record_type == FindRecordType.DELETED.value:
            return deleted_record_list, deleted_record_tx_id_list

        else:
            raise Exception('未处理的find_record_type！')

    @staticmethod
    def find_by_patient_id(patient_id, find_record_type=FindRecordType.NORMAL.value):
        """
        根据病人的ID查找其所有的就诊记录
        :param patient_id:
        :param find_record_type: 默认不去除被删除的记录
        :return:
        """
        tx_type = 'patient_record'
        id_name = 'patient_id'
        return MedicalRecordService.find_by_relation(tx_type, patient_id, id_name, find_record_type)

    @staticmethod
    def find_by_doctor_id(doctor_id, find_record_type=FindRecordType.NORMAL.value):
        """
        根据医生的ID查找其所有的就诊记录
        :param doctor_id:
        :param find_record_type: 默认不去除被删除的记录
        :return:
        """
        tx_type = 'doctor_record'
        id_name = 'doctor_id'
        return MedicalRecordService.find_by_relation(tx_type, doctor_id, id_name, find_record_type)

    @staticmethod
    def del_by_tx_id(tx_id, operator_type, operator_id):
        """
        根据tx_id来删除对应id的就诊记录，删除指的是新建一条medical_record_del交易单存入到区块链系统中
        :param tx_id:
        :param operator_type:
        :param operator_id:
        :return:
        """
        tx_dict = TransactionService.find_tx_by_id(tx_id)
        record_dict = tx_dict['content']
        patient_id = record_dict['patient_id']
        doctor_id = record_dict['doctor_id']
        medical_record_del = MedicalRecordDel(tx_id, operator_type, operator_id, patient_id, doctor_id)
        last_block_id = BlockService.add_block([TransactionService.gen_tx(medical_record_del)])
        return last_block_id

    @staticmethod
    def modify_record_fields(record_dict, rtn_fields_dict):
        """
        若record_dict与rtn_fields_dict中对应键的值不同，则用rtn_fields_dict中的值更新record_dict中的值
        :param record_dict:
        :param rtn_fields_dict:
        :return:
        """
        for key in rtn_fields_dict:
            if record_dict[key] != rtn_fields_dict[key]:
                record_dict[key] = rtn_fields_dict[key]

    @staticmethod
    def update_record(old_record_dict, new_record_dict, operator_type, operator_id):
        """
        保存更新后的就诊记录，以及新旧记录的关系
        :param old_record_dict:
        :param new_record_dict:
        :param operator_type:
        :param operator_id:
        :return:
        """
        old_record_dict = old_record_dict.copy()
        new_record_dict = new_record_dict.copy()
        # 利用 dict: new_record_dict 创建 MedicalRecord 对象
        if 'in_tx_id' in new_record_dict.keys():
            del new_record_dict['in_tx_id']
        if 'timestamp' in new_record_dict.keys():
            del new_record_dict['timestamp']

        new_record_obj = MedicalRecord(**new_record_dict)
        new_record_tx = TransactionService.gen_tx(new_record_obj)
        new_record_tx_id = new_record_tx.id

        # 构建用于保存更新时，新旧就诊记录关系的对象
        record_update = MedicalRecordUpdate(old_record_dict['in_tx_id'],
                                            new_record_tx_id, operator_type, operator_id,
                                            old_record_dict['patient_id'], old_record_dict['doctor_id'])
        record_update_tx = TransactionService.gen_tx(record_update)

        patient_record_tx = MedicalRecordService.gen_medical_patient_tx(new_record_obj.patient_id, new_record_tx_id)
        doctor_record_tx = MedicalRecordService.gen_medical_doctor_tx(new_record_obj.doctor_id, new_record_tx_id)

        last_block_id = BlockService.add_block([new_record_tx, patient_record_tx, doctor_record_tx, record_update_tx])
        return last_block_id
