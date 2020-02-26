#!/usr/bin/python -u
# -*- coding: utf-8 -*-

# GPL
# (c) 2020, Konstantin Shalygin <k0ste@k0ste.ru>

import requests
import warnings
import json
import argparse
import sys
import smtplib
import logging
from awsauth import S3Auth
from email.message import EmailMessage


class S3QuotaNotice(object):
    def __init__(self):
        parser = argparse.ArgumentParser(description="s3_quota_notice")
        parser.add_argument("-H", "--host", help="Server URL for the RadosGW API (example: http://objects.dreamhost.com/)", required=True)
        parser.add_argument("-k", "--insecure", help="Allow insecure server connections when using SSL", action="store_false")
        parser.add_argument("-e", "--admin_entry", help="The entry point for an admin request URL (default is '%(default)s')", default="admin")
        parser.add_argument("-a", "--access_key", help="S3 access key", required=True)
        parser.add_argument("-s", "--secret_key", help="S3 secret key", required=True)
        parser.add_argument("-q", "--quota_percent", help="Quota threshold percent (default is '%(default)s%%')", default="80")
        parser.add_argument("--smtp_host", help="SMTP host (default is '%(default)s')", default="localhost")
        parser.add_argument("--smtp_port", help="SMTP port (default is '%(default)s')", default=25)
        parser.add_argument("--smtp_starttls", help="SMTP auth with STARTTLS (default is '%(default)s')", action="store_true")
        parser.add_argument("--smtp_login", help="SMTP login")
        parser.add_argument("--smtp_password", help="SMTP password")
        parser.add_argument("--smtp_from", help="SMTP From header")
        parser.add_argument("--smtp_subject", help="SMTP Subject header (default is '%(default)s')", default="Cern S3 Storage quota notice")
        parser.add_argument("--smtp_signature", help="SMTP signature (default is '%(default)s')", default="Cern S3 service team")
        args = parser.parse_args()

        # helpers for default schema
        if not args.host.startswith("http"):
            args.host = "http://{0}".format(args.host)
        # and for request_uri
        if not args.host.endswith("/"):
            args.host = "{0}/".format(args.host)

        self.url = "{0}{1}/".format(args.host, args.admin_entry)

        if args.quota_percent.endswith("%"):
            args.quota_percent = args.quota_percent[:-1]

        self.host = args.host
        self.insecure = args.insecure
        self.access_key = args.access_key
        self.secret_key = args.secret_key
        self.quota_percent = int(args.quota_percent)
        self.smtp_host = args.smtp_host
        self.smtp_port = args.smtp_port
        self.smtp_starttls = args.smtp_starttls
        self.smtp_login = args.smtp_login
        self.smtp_password = args.smtp_password
        self.smtp_from = args.smtp_from
        self.smtp_subject = args.smtp_subject
        self.smtp_signature = args.smtp_signature

        self.logger()


    def logger(self):
        """
        Console Handler - for output to stdout.
        """

        root_logger = logging.getLogger()
        root_logger.setLevel(logging.INFO)
        log_formatter = logging.Formatter(fmt="[%(asctime)s] %(message)s",
                                          datefmt="%a %b %d %H:%M:%S %Z %Y")

        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setFormatter(log_formatter)
        root_logger.addHandler(console_handler)


    def bytes_to_human_readable(self, byte, suffix="B"):
        """
        Convert bytes to human readable sizes.
        """

        for unit in ['', 'Ki', 'Mi', 'Gi', 'Ti', 'Pi', 'Ei', 'Zi']:
            if abs(byte) < 1024.0:
                return byte, "{0}{1}".format(unit, suffix)
            byte /= 1024.0
        return byte, "{0}{1}".format('Yi', suffix)


    def make_rgw_query(self, endpoint, params=""):
      """
      Generic API requester.
      """

      url = "{0}{1}{2}".format(self.url, endpoint, params)

      try:
        # Inversion of condition, when '--insecure' is defined we disable
        # requests warning about certificate hostname mismatch.
        if not self.insecure:
            warnings.filterwarnings('ignore', message='Unverified HTTPS request')

        response = requests.get(url, verify=self.insecure,
                                auth=S3Auth(self.access_key,
                                self.secret_key,
                                self.host))

        if response.status_code == requests.codes.ok:
            return response.json()

        else:
            logging.error("RGW Error [{0}]: {1}".format(response.status_code,
                                                        response.content.decode('utf-8')))

      # DNS, connection errors, etc
      except requests.exceptions.RequestException as e:
          logging.error("RGW Error: {0}".format(e))


    def get_rgw_users(self):
        """
        API request to get users.
        """

        rgw_users = self.make_rgw_query("user", "?list")

        if rgw_users and 'keys' in rgw_users:
            return rgw_users['keys']
        else:
            # Compat with old Ceph versions (pre 12.2.3/13.2.9)
            rgw_metadata_users = self.make_rgw_query("metadata/user")
            return rgw_metadata_users

        return


    def get_rgw_user_info(self, uid):
        """
        API request to get user info & stats.
        """

        endpoint = "user"
        params = "?uid={0}&stats=True".format(uid)
        user_info = self.make_rgw_query(endpoint, params)

        if user_info:
            return user_info['email'], user_info['stats']

        return

    def get_rgw_user_quota(self, uid):
        """
        API request to get user quota.
        """

        endpoint = "user"
        params = "?quota&uid={0}&quota-type=user".format(uid)
        user_quota = self.make_rgw_query(endpoint, params)

        if user_quota:
            return user_quota

        return

    def check_rgw_user_quota(self, quota):
        """
        Method checks if quota enabled, than checks that quota size is defined,
        e.g. quota is not unlimited.
        """

        if quota['enabled'] and quota['max_size'] != -1:
            return True

        return


    def quota_usage_percent(self, bytes_used, quota_bytes):
        """
        Method return current usage of quota in percents.
        """

        return int(100 * (bytes_used / quota_bytes))


    def check_quota_usage(self, bytes_used, quota_bytes):
        """
        Method checks that quota is reached (in percents).
        """

        if self.quota_usage_percent(bytes_used, quota_bytes) >= self.quota_percent:
            return True

        return


    def email_connect(self):
        """
        SMTP connector.
        """

        try:
            self.smtp = smtplib.SMTP(self.smtp_host, self.smtp_port)
        except Exception as e:
            logging.error("SMTP Error: {0}".format(e))
            exit(2)

        self.smtp.ehlo()

        if self.smtp_starttls:
            try:
                self.smtp.starttls()
            except Exception as e:
                logging.error("SMTP Error: {0}".format(e))
                exit(2)

            self.smtp.ehlo()

        if self.smtp_login:
            try:
                self.smtp.login(self.smtp_login, self.smtp_password)
            except Exception as e:
                logging.error("SMTP Error: {0}".format(e))
                exit(2)


    def quota_reached_message(self, uid, quota, stats, email):
        """
        Method send email to S3 account email.
        """

        usage_percent = self.quota_usage_percent(stats['size_actual'], quota['max_size'])
        quota_bytes_human, quota_unit = self.bytes_to_human_readable(quota['max_size'])
        stats_bytes_human, stats_unit = self.bytes_to_human_readable(stats['size_actual'])
        quota_bytes_rounded = "{0:.2F}".format(quota_bytes_human)
        stats_bytes_rounded = "{0:.2F}".format(stats_bytes_human)

        message = """Hello user {0},

Your S3 usage has reached {1}% of your quota ({2}{3}).
Your current usage is: {4}{5}

Regards, {6}""".format(uid, usage_percent, quota_bytes_rounded,
                                        quota_unit,
                                        stats_bytes_rounded, stats_unit,
                                        self.smtp_signature)

        msg = EmailMessage()
        msg['Subject'] = self.smtp_subject
        msg['From'] = self.smtp_from
        msg['To'] = email
        msg.set_content(message)

        try:
            self.smtp.send_message(msg)
        except Exception as e:
            logging.error("SMTP Error: {0}".format(e))


    def worker(self):
        """
        Main looper.
        """
        rgw_users = self.get_rgw_users()
        self.email_connect()

        if rgw_users:
            for uid in rgw_users:
                quota = self.get_rgw_user_quota(uid)
                email, stats = self.get_rgw_user_info(uid)

                if self.check_rgw_user_quota(quota) and \
                    self.check_quota_usage(stats['size_actual'], quota['max_size']):
                        logging.info("Quota for uid '{0}' is reached. Current usage is {1}%.".format(uid, \
                            self.quota_usage_percent(stats['size_actual'], quota['max_size'])))
                        self.quota_reached_message(uid, quota, stats, email)
                else:
                    logging.info("Quota for uid '{0}' is not reached.".format(uid))


        self.smtp.quit()

def main():
    s3_quota_notice = S3QuotaNotice()
    s3_quota_notice.worker()

if __name__ == "__main__":
    main()
