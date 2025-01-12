import logging
from app.web_interface import WebInterface


if __name__ == "__main__":

  log = logging.getLogger('werkzeug')
  log.setLevel(logging.ERROR)
  
  app = WebInterface()
  app.run()
