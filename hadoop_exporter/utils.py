#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
import socket
import requests
import logging
import yaml
import argparse

EXPORTER_LOGS_DIR = os.environ.get('EXPORTER_LOGS_DIR', '/tmp/exporter')


def get_logger(name, log_file="hadoop_exporter.log"):
    '''
    define a common logger template to record log.
    @param name log module or object name.
    @return logger.
    '''

    logger = logging.getLogger(name)
    logger.setLevel(logging.DEBUG)

    if not os.path.exists(EXPORTER_LOGS_DIR):
        os.makedirs(EXPORTER_LOGS_DIR)

    fh = logging.FileHandler(os.path.join(EXPORTER_LOGS_DIR, log_file))
    fh.setLevel(logging.INFO)

    sh = logging.StreamHandler()
    sh.setLevel(logging.INFO)

    fmt = logging.Formatter(
        fmt='%(asctime)s %(filename)s[line:%(lineno)d]-[%(levelname)s]: %(message)s')
    fh.setFormatter(fmt)
    sh.setFormatter(fmt)

    logger.addHandler(fh)
    logger.addHandler(sh)
    return logger


logger = get_logger(__name__)


def get_metrics(url):
    '''
    :param url: The jmx url, e.g. http://host1:9870/jmx,http://host1:8088/jmx, http://host2:19888/jmx...
    :return a dict of all metrics scraped in the jmx url.
    '''
    result = []
    try:
        s = requests.session()
        response = s.get(url, timeout=5)
    except Exception as e:
        logger.warning("error in func: get_metrics, error msg: %s" % e)
        result = []
    else:
        if response.status_code != requests.codes.ok:
            logger.warning("get {0} failed, response code is: {1}.".format(
                url, response.status_code))
            result = []
        rlt = response.json()
        logger.debug(rlt)
        if rlt and "beans" in rlt:
            result = rlt['beans']
        else:
            logger.warning("no metrics get in the {0}.".format(url))
            result = []
    finally:
        s.close()
    return result


def get_host_ip():
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(('8.8.8.8', 80))
        ip = s.getsockname()[0]
    finally:
        s.close()
    return ip


def get_hostname():
    '''
    get hostname via socket.
    @return a string of hostname
    '''
    try:
        host = socket.getfqdn()
    except Exception as e:
        logger.info("get hostname failed, error msg: {0}".format(e))
        return None
    else:
        return host


def read_json_file(path_name, file_name):
    '''
    read metric json files.
    '''
    path = os.path.dirname(os.path.realpath(__file__))
    parent_path = os.path.dirname(path)
    metric_path = os.path.join(parent_path, path_name)
    metric_name = "{0}.json".format(file_name)
    try:
        with open(os.path.join(metric_path, metric_name), 'r') as f:
            metrics = yaml.safe_load(f)
            return metrics
    except Exception as e:
        logger.info("read metrics json file failed, error msg is: %s" % e)
        return {}


def get_file_list(file_path_name):
    '''
    This function is to get all .json file name in the specified file_path_name.
    @param file_path: The file path name, e.g. namenode, ugi, resourcemanager ...
    @return a list of file name.
    '''
    path = os.path.dirname(os.path.abspath(__file__))
    parent_path = os.path.dirname(path)
    json_path = os.path.join(parent_path, file_path_name)
    try:
        files = os.listdir(json_path)
    except OSError:
        logger.info("no such file or directory: '%s'" % json_path)
        return []
    else:
        rlt = []
        for i in range(len(files)):
            rlt.append(files[i].split(".json")[0])
        return rlt


def get_node_info(url):
    '''
    Firstly, I know how many nodes in the cluster.
    Secondly, exporter was installed in every node in the cluster.
    Therefore, how many services were installed in each node should be a key factor.
    In this function, a list of node info, including hostname, service jmx url should be returned.
    '''
    url = url.rstrip()
    host = get_hostname()
    node_info = {}
    try:
        s = requests.session()
        response = s.get(url, timeout=120)
    except Exception as e:
        logger.info(
            "error happened while requests url {0}, error msg : {1}".format(url, e))
        node_info = {}
    else:
        if response.status_code != requests.codes.ok:
            logger.info("get {0} failed, response code is: {1}.".format(
                url, response.status_code))
            node_info = {}
        result = response.json()
        logger.debug(result)
        if result:
            for k, v in result.items():
                for i in range(len(v)):
                    if host in v[i]:
                        node_info.setdefault(k, v[i][host])
                    else:
                        continue
            logger.debug(node_info)
        else:
            logger.info("No metrics get in the {0}.".format(url))
            node_info = {}
    finally:
        s.close()
    return node_info


def parse_args():

    parser = argparse.ArgumentParser(
        description='hadoop node exporter args, including url, metrics_path, address, port and cluster.'
    )
    parser.add_argument(
        '-cfg',
        required=False,
        dest='config',
        help='Exporter config file (defautl: None)',
        default=None
    )
    parser.add_argument(
        '-c',
        required=False,
        dest='cluster_name',
        help='Hadoop cluster labels. (default "hadoop_cluster")',
        default=None
    )
    parser.add_argument(
        '-nn',
        required=False,
        dest='namenode_jmx',
        help='Hadoop hdfs metrics URL. (example "http://localhost:9870/jmx")',
        default=None
    )
    parser.add_argument(
        '-dn',
        required=False,
        dest='datanode_jmx',
        help='Hadoop datanode metrics URL. (example "http://localhost:9864/jmx")',
        default=None
    )
    parser.add_argument(
        '-jn',
        required=False,
        dest='journalnode_jmx',
        help='Hadoop journalnode metrics URL. (example "http://localhost:8480/jmx")',
        default=None
    )
    parser.add_argument(
        '-rm',
        required=False,
        dest='resourcemanager_jmx',
        help='Hadoop resourcemanager metrics URL. (example "http://localhost:8088/jmx")',
        default=None
    )
    parser.add_argument(
        '-nm',
        required=False,
        dest='nodemanager_jmx',
        help='Hadoop nodemanager metrics URL. (example "http://localhost:8042/jmx")',
        default=None
    )
    parser.add_argument(
        '-mrjh',
        required=False,
        dest='mapred_jobhistory_jmx',
        help='Hadoop mapred history metrics URL. (example "http://localhost:19888/jmx")',
        default=None
    )
    parser.add_argument(
        '-hm',
        required=False,
        dest='hmaster_jmx',
        help='HBase masterserver metrics URL. (example "http://localhost:16010/jmx")',
        default=None
    )
    parser.add_argument(
        '-hr',
        required=False,
        dest='hregion_jmx',
        help='HBase regionserver metrics URL. (example "http://localhost:16030/jmx")',
        default=None
    )
    parser.add_argument(
        '-hs2',
        required=False,
        dest='hiveserver2_jmx',
        help='hive metrics URL. (example "http://localhost:10002/jmx")',
        default=None
    )
    parser.add_argument(
        '-hllap',
        required=False,
        dest='hivellap_jmx',
        help='Hadoop llap metrics URL. (example "http://localhost:15002/jmx")',
        default=None
    )
    parser.add_argument(
        '-ad',
        required=False,
        dest='auto_discovery',
        help='Enable auto discovery if set true else false. (example "--auto true") (default: false)',
        default=None
    )
    parser.add_argument(
        '-adw',
        required=False,
        dest='discovery_whitelist',
        help='Enable auto discovery if set true else false. (example "--auto true") (default: false)',
        default=None
    )
    parser.add_argument(
        '-addr',
        dest='address',
        required=False,
        help='Polling server on this address. (default "127.0.0.1")',
        default=None
    )
    parser.add_argument(
        '-p',
        dest='port',
        required=False,
        type=int,
        help='Listen to this port. (default "9130")',
        default=None
    )
    parser.add_argument(
        '--path',
        dest='path',
        required=False,
        help='Path under which to expose metrics. (default "/metrics")',
        default=None
    )
    parser.add_argument(
        '--period',
        dest='period',
        required=False,
        type=int,
        help='Period (seconds) to consume jmx service. (default: 30)',
        default=None
    )
    return parser.parse_args()
