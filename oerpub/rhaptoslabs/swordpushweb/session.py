class Session(object):
    """ Base class for oerpub sessions. """

class AnonymousSession(Session):
    """ Class for anonymous users. """

    username = 'anonymous'
    password = ''
    workspace_title = "Connexions"
    sword_version = "2.0"
    maxuploadsize = "0"
    collections = []

class TestingSession(AnonymousSession):
    pass

class CnxSession(Session):
    """ Class that stores information about a cnx user's login. """
    def __init__(self, username, password, service_document_url,
            workspace_title, sword_version, maxuploadsize, collections):
        self.username = username
        self.password = password
        self.service_document_url = service_document_url
        self.workspace_title = workspace_title
        self.sword_version = sword_version
        self.maxuploadsize = maxuploadsize
        self.collections = collections