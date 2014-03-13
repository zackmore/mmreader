import os.path
import json
import tornado.web
import tornado.httpserver
import tornado.ioloop
import tornado.options

from model import *
from helper import *
import config

from tornado.options import define, options
define('port', default=9999, help='run on the given port', type=int)

class Application(tornado.web.Application):
    def __init__(self):
        handlers = [
            (r'/', MainHandler),
            (r'/feed/(\d+)', FeedHandler),
            (r'/item/(\d+)', ItemHandler),
            (r'/login', LoginHandler),
            (r'/logout', LogoutHandler),
        ]
        settings = dict(
            template_path=os.path.join(os.path.dirname(__file__),
                                        'templates'),
            static_path=os.path.join(os.path.dirname(__file__),
                                        'templates/static'),
            ui_modules={'Sidebar': SidebarModule},
            cookie_secret='1234',
            #xsrf_cookies=True,
            debug=True
        )
        tornado.web.Application.__init__(self, handlers, **settings)
        self.db = scoped_session(sessionmaker(bind=engine))


class BaseHandler(tornado.web.RequestHandler):
    def get_current_user(self):
        user_id = self.get_secure_cookie('uid')
        if user_id:
            try:
                user = self.db.query(Admin).filter_by(userid=user_id).one()
            except NoResultFound:
                return
            else:
                return user

    @property
    def db(self):
        return self.application.db


class SidebarModule(tornado.web.UIModule):
    def render(self):
        all_feeds = self.handler.db.query(Feed).order_by(Feed.feedid)
        return self.render_string('sidebar.html',
                                    all_feeds=all_feeds,
                                    admin_user=self.current_user)


class LoginHandler(BaseHandler):
    def post(self):
        if self.current_user:
            return

        username = self.get_argument('username')
        password = self.get_argument('password')

        result = self.db.query(Admin).\
                filter_by(username=username).\
                filter_by(password=password)

        if result.count():
            self.set_secure_cookie('uid', str(result.one().userid))
        self.redirect('/')


class LogoutHandler(BaseHandler):
    def get(self):
        if self.current_user:
            self.clear_cookie('uid')
        self.redirect('/')


class MainHandler(BaseHandler):
    def get(self):
        per_page = config.Index_per_page
        page_number = int(self.get_argument('more', 0))
        all_items_number = self.db.query(Item).count()
        pagination = Pagination(page_number, all_items_number, per_page)

        mode = self.get_argument('mode', 'normal')
        if mode == 'all':
            newest_items = self.db.query(Item).\
                            order_by(Item.pubdate.desc()).\
                            offset(pagination.start_point).\
                            limit(pagination.per_page)
        elif mode == 'normal':
            newest_items = self.db.query(Item).\
                            filter_by(readed=False).\
                            order_by(Item.pubdate.desc()).\
                            offset(pagination.start_point).\
                            limit(pagination.per_page)

        self.render('list.html',
                    newest_items=newest_items,
                    pagination=pagination,
                    admin_user=self.current_user)


class FeedHandler(BaseHandler):
    def get(self, feedid):
        per_page = config.Index_per_page
        page_number = int(self.get_argument('more', 0))
        all_items_number = self.db.query(Item).filter_by(feedid=feedid).count()
        pagination = Pagination(page_number, all_items_number, per_page)

        items = self.db.query(Item).filter_by(feedid=feedid).\
                order_by(Item.pubdate.desc()).\
                offset(pagination.page_number).\
                limit(pagination.per_page)

        self.render('list.html',
                    newest_items=items,
                    pagination=pagination,
                    admin_user=self.current_user)


class ItemHandler(BaseHandler):
    def get(self, itemid):
        item = self.db.query(Item).filter_by(itemid=itemid).one()

        if self.current_user:
            if not item.readed:
                item.readed = True
                item.feed.itemunread -= 1
                self.db.add(item)
                self.db.commit()

        self.render('article.html', article=item)


if __name__ == '__main__':
    tornado.options.parse_command_line()
    http_server = tornado.httpserver.HTTPServer(Application())
    http_server.listen(options.port)

    tornado.ioloop.IOLoop.instance().start()
