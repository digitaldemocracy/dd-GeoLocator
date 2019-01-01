import MySQLdb

class DAO:

    def __init__(self):
        pass

    def init_app(self, app):
        self.app = app

    def make_connection(self):
        with self.app.app_context():
            return MySQLdb.connect(host=self.app.config['DB_HOST'],
                                   user=self.app.config['DB_USER'],
                                   passwd=self.app.config['DB_PASSWORD'],
                                   db=self.app.config['DB_NAME'],
                                   charset='utf8',
                                   use_unicode = True)

