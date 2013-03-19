import os
import types
import shutil
import datetime
import zipfile
import traceback
import json
import logging
import libxml2
import lxml
import re
import mimetypes
from BeautifulSoup import BeautifulSoup
import MySQLdb as mdb
from cStringIO import StringIO
import peppercorn
import codecs
from pkg_resources import resource_filename
from lxml import etree
from pyramid.view import view_config
from pyramid.httpexceptions import HTTPFound
from pyramid.renderers import render_to_response, get_renderer
from pyramid.response import Response
from pyramid.decorator import reify
from pyramid.threadlocal import get_current_registry
import formencode
from pyramid_simpleform import Form
from pyramid_simpleform.renderers import FormRenderer
from languages import languages
from oerpub.rhaptoslabs import sword2cnx
from rhaptos.cnxmlutils.odt2cnxml import transform
from rhaptos.cnxmlutils.validatecnxml import validate
from oerpub.rhaptoslabs.cnxml2htmlpreview.cnxml2htmlpreview import cnxml_to_htmlpreview
from oerpub.rhaptoslabs.cnxml2htmlpreview.html2cnxml import html_to_cnxml
import gdata.gauth
import gdata.docs.client
from oerpub.rhaptoslabs.html_gdocs2cnxml.gdocs_authentication import getAuthorizedGoogleDocsClient
from oerpub.rhaptoslabs.html_gdocs2cnxml.gdocs2cnxml import gdocs_to_cnxml
import urllib2
import urllib
from oerpub.rhaptoslabs.html_gdocs2cnxml.htmlsoup2cnxml import htmlsoup_to_cnxml
from rhaptos.cnxmlutils.utils import aloha_to_html, html_to_valid_cnxml
from oerpub.rhaptoslabs.latex2cnxml.latex2cnxml import latex_to_cnxml
from oerpub.rhaptoslabs.slideimporter.slideshare import upload_to_slideshare, get_details, get_slideshow_download_url, get_transcript, fetch_slideshow_status
from oerpub.rhaptoslabs.slideimporter.google_presentations import GooglePresentationUploader,GoogleOAuth
from utils import load_config, save_config, add_directory_to_zip
from utils import escape_system, clean_cnxml
from utils import get_cnxml_from_zipfile, add_featuredlinks_to_cnxml
from utils import get_files_from_zipfile, build_featured_links
from utils import create_module_in_2_steps
import convert as JOD # Imports JOD convert script
import jod_check #Imports script which checks to see if JOD is running
from z3c.batching.batch import Batch

from utils import check_login, get_metadata_from_repo
from utils import ZIP_PACKAGING
from helpers import BaseHelper 
from .editor import EditorHelper

TESTING = False      
import oauth2client, oauth2client.client
from oauth2client.client import OAuth2WebServerFlow
from oauth2client.file import Storage
import httplib2
from apiclient.discovery import build

class LoginSchema(formencode.Schema):
    allow_extra_fields = True
    service_document_url = formencode.validators.String(not_empty=True)
    username = formencode.validators.PlainText(not_empty=True)
    password = formencode.validators.NotEmpty()

@view_config(route_name='oauth2')
def oauth2(request):
    check_login(request)
    token_request_uri = "https://accounts.google.com/o/oauth2/auth"
    response_type = "code"
    client_id= "640541804881.apps.googleusercontent.com"
    client_secret = "7cI9ZfiG5wbZk_EP_TSAXEF8"
    redirect_uri = "http://r2d1.oerpub.org/googlelogin"
    scope = "https://www.googleapis.com/auth/userinfo.profile https://www.googleapis.com/auth/userinfo.email https://www.googleapis.com/auth/drive https://www.googleapis.com/auth/drive.file"
    url ="{token_request_uri}?response_type={response_type}&client_id={client_id}&redirect_uri={redirect_uri}&scope={scope}".format(
            token_request_uri = token_request_uri,
            response_type = response_type,
            client_id = client_id,
            redirect_uri = redirect_uri,
            scope = scope)
    flow = OAuth2WebServerFlow(client_id=client_id,client_secret=client_secret,scope=scope,redirect_uri=redirect_uri)
    new_url = auth_uri = flow.step1_get_authorize_url()
    request.session['flow']=flow
    return HTTPFound(new_url)

@view_config(route_name='googlelogin')
def googlelogin(request):
    if 'error' in request.GET or 'code' not in request.GET:
        login_failed_url='/'
        return HTTPFound('{loginfailed}'.format(loginfailed = login_failed_url))
    code = request.GET['code']
    flow=request.session['flow']
    credentials = flow.step2_exchange(code)
    credentials_location = "/var/www/credentials/"+request.session['username']
    storage = Storage("/root/master/credentials/saket_credentials")
    storage.put(credentials)
    http = httplib2.Http()
    http = credentials.authorize(http)
    service = build('drive','v2',http=http)
    files = (service.files().list().execute())
    print files['items']
    templatePath = 'templates/cnxlogin.pt'
    response = {
        'username': request.session['username'],
        'password': request.session['password'],
        'login_url': login_url,
    }
    return render_to_response(templatePath, response, request=request)
@view_config(route_name='login')
def login_view(request):
    """
    Perform a 'login' by getting the service document from a sword repository.
    """

    templatePath = 'templates/login.pt'

    config = load_config(request)
    form = Form(request, schema=LoginSchema)
    field_list = [
        ('username',),
        ('password',),
    ]

    session = request.session

    # validate the form in order to compute all errors
    valid_form = form.validate()
    request['errors'] = form.all_errors()

    # Check for successful form completion
    if 'form.submitted' in request.POST and valid_form:
        # The login details are persisted on the session
        for field_name in [i[0] for i in field_list]:
            session[field_name] = form.data[field_name]
        session['service_document_url'] = form.data['service_document_url']
        loggedIn = True
    # Check if user is already authenticated
    else:
        loggedIn = True
        for key in ['username', 'password', 'service_document_url', 'collections', 'workspace_title', 'sword_version', 'maxuploadsize']:
            if not session.has_key(key):
                loggedIn = False
        if loggedIn:
            return HTTPFound(location=request.route_url('choose'))

    # TODO: check credentials against Connexions and ask for login
    # again if failed.

    # If not signed in, go to login page
    if not loggedIn:
        response = {
            'form': FormRenderer(form),
            'field_list': field_list,
            'config': config,
        }
        return render_to_response(templatePath, response, request=request)

    # Here we know that the user is authenticated and that they did so
    # by logging in (rather than having had a cookie set already)
    if TESTING:
        session['workspace_title'] = "Connexions"
        session['sword_version'] = "2.0"
        session['maxuploadsize'] = "60000"
        session['collections'] = [{'title': 'Personal Workspace', 'href': 'http://'}]
    else:
        # Get the service document and persist what's needed.
        conn = sword2cnx.Connection(session['service_document_url'],
                                    user_name=session['username'],
                                    user_pass=session['password'],
                                    always_authenticate=True,
                                    download_service_document=True)
        try:
            # Get available collections from SWORD service document
            # We create a list of dictionaries, otherwise we'll have problems
            # pickling them.
            if not conn.sd.valid:
                raise Exception
            session['collections'] = [{'title': i.title, 'href': i.href}
                                      for i in sword2cnx.get_workspaces(conn)]
        except:
            del session['username']
            del session['password']
            request['errors'] = ["Invalid username or password. Please try again.",]
            response = {
                'form': FormRenderer(form),
                'field_list': field_list,
                'config': config,
            }
            return render_to_response(templatePath, response, request=request)

        # Get needed info from the service document
        doc = etree.fromstring(conn.sd.raw_response)

        # Prep the namespaces. xpath does not like a None namespace.
        namespaces = doc.nsmap
        del namespaces[None]

        # We need some details from the service document.
        # TODO: This is fragile, since it assumes a certain structure.
        session['workspace_title'] = doc.xpath('//atom:title',
                                               namespaces=namespaces
                                               )[0].text
        session['sword_version'] = doc.xpath('//sword:version',
                                             namespaces=namespaces
                                             )[0].text
        session['maxuploadsize'] = doc.xpath('//sword:maxuploadsize',
                                             namespaces=namespaces
                                             )[0].text

    # Go to the upload page
    return HTTPFound(location=request.route_url('choose'))


@view_config(route_name='cnxlogin')
def cnxlogin_view(request):
    check_login(request)

    config = load_config(request)
    login_url = config['login_url']

    templatePath = 'templates/cnxlogin.pt'
    response = {
        'username': request.session['username'],
        'password': request.session['password'],
        'login_url': login_url,
    }
    return render_to_response(templatePath, response, request=request)


@view_config(route_name='logout', renderer='templates/login.pt')
def logout_view(request):
    session = request.session
    session.invalidate()
    raise HTTPFound(location=request.route_url('login'))


class UploadSchema(formencode.Schema):
    allow_extra_fields = True
    upload = formencode.validators.FieldStorageUploadConverter()

class ImporterSchema(formencode.Schema):
    allow_extra_fields = True
    importer = formencode.validators.FieldStorageUploadConverter()
    #upload_to_ss = formencode.validators.String()
    #upload_to_google = formencode.validators.String()
    #introductory_paragraphs = formencode.validators.String()

class ImporterChoiceSchema(formencode.Schema):
    allow_extra_fields = True
    upload_to_ss = formencode.validators.String()
    upload_to_google = formencode.validators.String()
    #introductory_paragraphs = formencode.validators.String()
class QuestionAnswerSchema(formencode.Schema):
	allow_extra_fields = True
	#question1 = formencode.validators.String()
	#options1 = formencode.validators.String()
	#solution1 = formencode.validators.String()

class ConversionError(Exception):
    def __init__(self, msg):
        self.msg = msg
    def __str__(self):
        return self.msg

def save_and_backup_file(save_dir, filename, content, mode='w'):
    """ save a file, but first make a backup if the file exists
    """
    if isinstance(content, unicode):
        content = content.encode('ascii', 'xmlcharrefreplace')
    filename = os.path.join(save_dir, filename)
    if os.path.exists(filename):
        os.rename(filename, filename + '~')
    f = open(filename, mode)
    f.write(content)
    f.close()

def append_zip(zipfilename, filename, content):
    """ Append files to a zip file. files is a list of tuples where each tuple
        is a (filename, content) pair. """
    zip_archive = zipfile.ZipFile(zipfilename, 'a')
    zip_archive.writestr(filename, content)
    zip_archive.close()

def save_zip(save_dir, cnxml, html, files):
    ram = StringIO()
    zip_archive = zipfile.ZipFile(ram, 'w')
    zip_archive.writestr('index.cnxml', cnxml)
    if html is not None:
        # Add a head and css to the html. Also add #canvas to the body
        # so the css that was constructed to work with the editor nested
        # in that element continues to work.
        tree = etree.fromstring(html, etree.HTMLParser())
        xslt = etree.XML("""\
            <xsl:stylesheet xmlns:xsl="http://www.w3.org/1999/XSL/Transform" version="1.0">
                <xsl:template match="/html">
                    <html><xsl:copy-of select="@*"/>
                    <head>
                      <link rel="stylesheet" type="text/css" href="oerpub.css" />
                      <script type="text/javascript" src="http://cdn.mathjax.org/mathjax/latest/MathJax.js?config=TeX-MML-AM_HTMLorMML-full"></script>
                      <script type="text/javascript" src="oerpub.js"></script>
                      <script type="text/x-mathjax-config">MathJax.Hub.Config({
                        jax: ["input/MathML", "input/TeX", "input/AsciiMath", "output/NativeMML", "output/HTML-CSS"],
                        extensions: ["asciimath2jax.js", "tex2jax.js","mml2jax.js","MathMenu.js","MathZoom.js"],
                        tex2jax: { inlineMath: [["[TEX_START]","[TEX_END]"], ["\\\\(", "\\\\)"]] },
                        MMLorHTML: {prefer:{MSIE:"HTML",Firefox:"HTML",Opera:"HTML",Chrome:"HTML",Safari:"HTML",other:"HTML"}},
                        TeX: {
                          extensions: ["AMSmath.js","AMSsymbols.js","noErrors.js","noUndefined.js"], noErrors: { disabled: true }
                        },
                        AsciiMath: { noErrors: { disabled: true } }
                      });</script>
                    </head>
                    <xsl:apply-templates />
                    </html>
                </xsl:template>
                <xsl:template match="body">
                    <body>
                        <xsl:copy-of select="@*"/>
                        <xsl:attribute name="id">
                            <xsl:text>canvas</xsl:text>
                        </xsl:attribute>
                        <xsl:apply-templates />
                    </body>
                </xsl:template>
                <xsl:template match="@*|node()">
                    <xsl:copy><xsl:apply-templates select="@*|node()"/></xsl:copy>
                </xsl:template>
            </xsl:stylesheet>""")
        html = str(etree.XSLT(xslt)(tree))
        zip_archive.writestr('index.html', html)
        # Add the css file itself
        registry = get_current_registry()
        f1 = os.path.join(registry.settings['aloha.editor'], 'css', 'html5_metacontent.css')
        f2 = os.path.join(registry.settings['aloha.editor'], 'css', 'html5_content_in_oerpub.css')
        zip_archive.writestr('oerpub.css', open(f1, 'r').read() + open(f2, 'r').read())

    for filename, fileObj in files:
        zip_archive.writestr(filename, fileObj)
    zip_archive.close()
    zip_filename = os.path.join(save_dir, 'upload.zip')
    save_and_backup_file(save_dir, zip_filename, ram.getvalue(), mode='wb')

def save_cnxml(save_dir, cnxml, files):
    # write CNXML output
    save_and_backup_file(save_dir, 'index.cnxml', cnxml)

    # write files
    for filename, content in files:
        filename = os.path.join(save_dir, filename)
        f = open(filename, 'wb') # write binary, important!
        f.write(content)
        f.close()

    # we generate the preview and save the error
    conversionerror = None
    try:
        htmlpreview = cnxml_to_htmlpreview(cnxml)
    except libxml2.parserError:
        conversionerror = traceback.format_exc()

    # Zip up all the files. This is done now, since we have all the files
    # available, and it also allows us to post a simple download link.
    # Note that we cannot use zipfile as context manager, as that is only
    # available from python 2.7
    # TODO: Do a filesize check xxxx
    if conversionerror is None:
        save_and_backup_file(save_dir, 'index.html', htmlpreview)
        save_zip(save_dir, cnxml, htmlpreview, files)
    else:
        save_zip(save_dir, cnxml, None, files)
        raise ConversionError(conversionerror)

def validate_cnxml(cnxml):
    valid, log = validate(cnxml, validator="jing")
    if not valid:
        raise ConversionError(log)

def render_conversionerror(request, error):
    templatePath = 'templates/conv_error.pt'
    fname='gdoc'
    if 'filename' in request.session:
        fname=request.session['filename']
    response = {'filename' : fname, 'error': error}

    # put the error on the session for retrieval on the editor
    # view
    request.session['transformerror'] = error

    if('title' in request.session):
        del request.session['title']
    return render_to_response(templatePath, response, request=request)

def process_gdocs_resource(save_dir, gdocs_resource_id, gdocs_access_token=None):
    """
    # login to gdocs and get a client object
    gd_client = getAuthorizedGoogleDocsClient()

    # Create a AuthSub Token based on gdocs_access_token String
    auth_sub_token = gdata.gauth.AuthSubToken(gdocs_access_token) \
                     if gdocs_access_token \
                     else None

    # get the Google Docs Entry
    gd_entry = gd_client.GetDoc(gdocs_resource_id, None, auth_sub_token)

    # Get the contents of the document
    gd_entry_url = gd_entry.content.src
    html = gd_client.get_file_content(gd_entry_url, auth_sub_token)
    """
    storage=Storage("/root/master/saket_credentials.json")
    credentials = storage.get()

    http = httplib2.Http()
    http = credentials.authorize(http)
    service = build('drive','v2',http=http)
    file = service.files().get(fileId=gdocs_resource_id).execute()
    html = file['title']
    print "**********************"
    print html
    print "**********************"

    # Transformation and get images
    cnxml, objects = gdocs_to_cnxml(html, bDownloadImages=True)

    cnxml = clean_cnxml(cnxml)
    save_cnxml(save_dir, cnxml, objects.items())

    validate_cnxml(cnxml)

    # Return the title and filename.  Old comment states
    # that returning this filename might kill the ability to
    # do multiple tabs in parallel, unless it gets offloaded
    # onto the form again.
    return (gd_entry.title.text, "Google Document")


@view_config(route_name='choose')
def choose_view(request):
    check_login(request)
    session = request.session

    templatePath = 'templates/choose.pt'

    form = Form(request, schema=UploadSchema)
    presentationform = Form(request, schema=ImporterSchema)
    field_list = [('upload', 'File')]

    # clear the session
    if 'transformerror' in request.session:
        del request.session['transformerror']
    if 'title' in request.session:
        del request.session['title']

    # Check for successful form completion
    print form.all_errors()
    print presentationform.all_errors()

    if form.validate():
        print "NORMAL FORM"
        try: # Catch-all exception block
            # Create a directory to do the conversions
            now_string = datetime.datetime.now().strftime('%Y%m%d-%H%M%S')
            # TODO: This has a good chance of being unique, but even so...
            temp_dir_name = '%s-%s' % (request.session['username'], now_string)
            save_dir = os.path.join(
                request.registry.settings['transform_dir'],
                temp_dir_name
                )
            os.mkdir(save_dir)

            # Keep the info we need for next uploads.  Note that this
            # might kill the ability to do multiple tabs in parallel,
            # unless it gets offloaded onto the form again.
            request.session['upload_dir'] = temp_dir_name
            if form.data['upload'] is not None:
                request.session['filename'] = form.data['upload'].filename

            # Google Docs Conversion
            # if we have a Google Docs ID and Access token.
            if form.data['gdocs_resource_id']:
                gdocs_resource_id = form.data['gdocs_resource_id']
                gdocs_access_token = form.data['gdocs_access_token']

                form.data['gdocs_resource_id'] = None
                form.data['gdocs_access_token'] = None

                (request.session['title'], request.session['filename']) = \
                    process_gdocs_resource(save_dir, \
                                           gdocs_resource_id)
                                           # , gdocs_access_token) # Google Docs authentication does not work anymore 2012-11-09

            # HTML URL Import:
            elif form.data.get('url_text'):
                url = form.data['url_text']

                form.data['url_text'] = None

                # Build a regex for Google Docs URLs
                regex = re.compile("^https:\/\/docs\.google\.com\/.*document\/[^\/]\/([^\/]+)\/")
                r = regex.search(url)

                # Take special action for Google Docs URLs
                if r:
                    gdocs_resource_id = r.groups()[0]
                    (request.session['title'], request.session['filename']) = \
                        process_gdocs_resource(save_dir, "document:" + gdocs_resource_id)
                else:
                    # download html:
                    #html = urllib2.urlopen(url).read()
                    # Simple urlopen() will fail on mediawiki websites like e.g. Wikipedia!
                    import_opener = urllib2.build_opener()
                    import_opener.addheaders = [('User-agent', 'Mozilla/5.0')]
                    try:
                        import_request = import_opener.open(url)
                        html = import_request.read()

                        # transformation
                        cnxml, objects, html_title = htmlsoup_to_cnxml(
                        html, bDownloadImages=True, base_or_source_url=url)
                        request.session['title'] = html_title

                        cnxml = clean_cnxml(cnxml)
                        save_cnxml(save_dir, cnxml, objects.items())

                        # Keep the info we need for next uploads.  Note that
                        # this might kill the ability to do multiple tabs in
                        # parallel, unless it gets offloaded onto the form
                        # again.
                        request.session['filename'] = "HTML Document"

                        validate_cnxml(cnxml)

                    except urllib2.URLError, e:
                        request['errors'] = ['The URL %s could not be opened' %url,]
                        response = {
                            'form': FormRenderer(form),
                            }
                        return render_to_response(templatePath, response, request=request)

            # Office, CNXML-ZIP or LaTeX-ZIP file
            else:
                # Save the original file so that we can convert, plus keep it.
                original_filename = str(os.path.join(
                    save_dir,
                    form.data['upload'].filename.replace(os.sep, '_')))
                saved_file = open(original_filename, 'wb')
                input_file = form.data['upload'].file
                shutil.copyfileobj(input_file, saved_file)
                saved_file.close()
                input_file.close()

                form.data['upload'] = None

                # Check if it is a ZIP file with at least index.cnxml or a LaTeX file in it
                try:
                    zip_archive = zipfile.ZipFile(original_filename, 'r')
                    is_zip_archive = ('index.cnxml' in zip_archive.namelist())

                    # Do we have a latex file?
                    if not is_zip_archive:
                        # incoming latex.zip must contain a latex.tex file, where "latex" is the base name.
                        (latex_head, latex_tail) = os.path.split(original_filename)
                        (latex_root, latex_ext)  = os.path.splitext(latex_tail)
                        latex_basename = latex_root
                        latex_filename = latex_basename + '.tex'
                        is_latex_archive = (latex_filename in zip_archive.namelist())

                except zipfile.BadZipfile:
                    is_zip_archive = False
                    is_latex_archive = False

                # ZIP package from previous conversion
                if is_zip_archive:
                    # Unzip into transform directory
                    zip_archive.extractall(path=save_dir)

                    # Rename ZIP file so that the user can download it again
                    os.rename(original_filename, os.path.join(save_dir, 'upload.zip'))

                    # Read CNXML
                    with open(os.path.join(save_dir, 'index.cnxml'), 'rt') as fp:
                        cnxml = fp.read()

                    # Convert the CNXML to XHTML for preview
                    html = cnxml_to_htmlpreview(cnxml)
                    with open(os.path.join(save_dir, 'index.html'), 'w') as index:
                        index.write(html)

                    cnxml = clean_cnxml(cnxml)
                    validate_cnxml(cnxml)

                # LaTeX
                elif is_latex_archive:
                    f = open(original_filename)
                    latex_archive = f.read()

                    # LaTeX 2 CNXML transformation
                    cnxml, objects = latex_to_cnxml(latex_archive, original_filename)

                    cnxml = clean_cnxml(cnxml)
                    save_cnxml(save_dir, cnxml, objects.items())
                    validate_cnxml(cnxml)

                # OOo / MS Word Conversion
                else:
                    # Convert from other office format to odt if needed
                    filename, extension = os.path.splitext(original_filename)
	            odt_filename = str(filename) + '.odt'

                    if(extension != '.odt'):
                        converter = JOD.DocumentConverterClient()
                        # Checks to see if JOD is active on the machine. If it is the conversion occurs using JOD else it converts using OO headless
                        command = None
                        if jod_check.check('office[0-9]'):
                            try:
                                converter.convert(original_filename, 'odt', filename + '.odt')
                            except Exception as e:
                                print e
                        else:
                            odt_filename= '%s.odt' % filename
                            command = '/usr/bin/soffice -headless -nologo -nofirststartwizard "macro:///Standard.Module1.SaveAsOOO(' + escape_system(original_filename)[1:-1] + ',' + odt_filename + ')"'
                            os.system(command)
                        try:
                            fp = open(odt_filename, 'r')
                            fp.close()
                        except IOError as io:
                            if command == None:
                                raise ConversionError("%s not found" %
                                                      odt_filename)
                            else:
                                raise ConversionError("%s not found because command \"%s\" failed" %
                                                      (odt_filename,command) )
                    
                    # Convert and save all the resulting files.

                    tree, files, errors = transform(odt_filename)
                    cnxml = clean_cnxml(etree.tostring(tree))

                    save_cnxml(save_dir, cnxml, files.items())

                    # now validate with jing
                    validate_cnxml(cnxml)

        except ConversionError as e:
            return render_conversionerror(request, e.msg)

        except Exception:
            # Record traceback
            tb = traceback.format_exc()
            # Get software version from git
            try:
                import subprocess
                p = subprocess.Popen(["git","log","-1"], stdout=subprocess.PIPE)
                out, err = p.communicate()
                commit_hash = out[:out.find('\n')]
            except OSError:
                commit_hash = 'None'
            # Get timestamp
            timestamp = datetime.datetime.now()
            # Zip up error report, form data, uploaded file (if any)  and temporary transform directory
            zip_filename = os.path.join(request.registry.settings['errors_dir'], temp_dir_name + '.zip')
            zip_archive = zipfile.ZipFile(zip_filename, 'w')
            zip_archive.writestr("info.txt", """TRACEBACK
""" + tb + """
GIT VERSION
""" + commit_hash + """

USER
""" + request.session['username'] + """

SERVICE DOCUMENT URL
""" + request.session['service_document_url'] + """

TIMESTAMP
""" + str(timestamp) + """

FORM DATA
""" + '\n'.join([key + ': ' + str(form.data.get(key)) for key in ['gdocs_resource_id', 'gdocs_access_token', 'url_text']]) + "\n")
            add_directory_to_zip(temp_dir_name, zip_archive, basePath=request.registry.settings['transform_dir'])

            templatePath = 'templates/error.pt'
            response = {
                'traceback': tb,
            }
            if('title' in request.session):
                del request.session['title']
            return render_to_response(templatePath, response, request=request)

#            tmp_obj = render_to_response(templatePath, response, request=request)
#            return tmp_obj

        request.session.flash('The file was successfully converted.')
        return HTTPFound(location=request.route_url('preview'))

    # First view or errors
    elif presentationform.validate():
        now_string = datetime.datetime.now().strftime('%Y%m%d-%H%M%S')
        print "Inside presentation form"
        temp_dir_name = '%s-%s' % (request.session['username'], now_string)
        save_dir = os.path.join(
            request.registry.settings['slideshare_import_dir'],
            temp_dir_name
        )
        os.mkdir(save_dir)
        uploaded_filename = form.data['importer'].filename.replace(os.sep, '_')
        original_filename = os.path.join(save_dir, form.data['importer'].filename.replace(os.sep, '_'))
        saved_file = open(original_filename, 'wb')
        input_file = form.data['importer'].file
        shutil.copyfileobj(input_file, saved_file)
        saved_file.close()
        input_file.close()
        username = session['username']

        zipped_filepath = os.path.join(save_dir,"cnxupload.zip")
        print "Ziiped filepath",zipped_filepath
        session['userfilepath'] = zipped_filepath
        zip_archive = zipfile.ZipFile(zipped_filepath, 'w')
        zip_archive.write(original_filename,uploaded_filename)
        zip_archive.close()
        session['uploaded_filename'] = uploaded_filename
        session['original_filename'] = original_filename
        print "Original filename ",original_filename
        username = session['username']
        #slideshare_details = get_details(slideshow_id)
        #slideshare_download_url = get_slideshow_download_url(slideshare_details)
        #session['transcript'] = get_transcript(slideshare_details)
        session['title'] = uploaded_filename.split(".")[0]
        metadata = {}
        metadata['dcterms:title'] = uploaded_filename.split(".")[0]
        cnxml = """<document xmlns="http://cnx.rice.edu/cnxml" xmlns:md="http://cnx.rice.edu/mdml" xmlns:bib="http://bibtexml.sf.net/" xmlns:m="http://www.w3.org/1998/Math/MathML" xmlns:q="http://cnx.rice.edu/qml/1.0" id="new" cnxml-version="0.7" module-id="new">
  <title>"""+session['title']+"""</title>
<metadata xmlns:md="http://cnx.rice.edu/mdml" mdml-version="0.5">
  <!-- WARNING! The 'metadata' section is read only. Do not edit below.
       Changes to the metadata section in the source will not be saved. -->
  <md:repository>http://cnx.org/content</md:repository>
  <md:content-id>new</md:content-id>
  <md:title>""</md:title>
  <md:version>**new**</md:version>
  <md:created>2012/06/22 03:49:41.962 GMT-5</md:created>
  <md:revised>2012/06/22 03:49:42.716 GMT-5</md:revised>
 <md:actors>
<md:person userid="""+"\""+username+"\""+""">
<md:firstname></md:firstname>
<md:surname></md:surname>
<md:fullname></md:fullname>
<md:email></md:email>
</md:person>
</md:actors>
<md:roles>

<md:role type="maintainer">"""+username+"""</md:role>
<md:role type="licensor">"""+username+"""</md:role>
</md:roles>
<md:license url="http://creativecommons.org/licenses/by/3.0/"/>
<!-- For information on license requirements for use or modification, see license url in the
above <md:license> element.
For information on formatting required attribution, see the URL:
CONTENT_URL/content_info#cnx_cite_header
where CONTENT_URL is the value provided above in the <md:content-url> element.
-->

<md:language>en</md:language>
<!-- WARNING! The 'metadata' section is read only. Do not edit above.
Changes to the metadata section in the source will not be saved. -->
</metadata>"""
        for key in metadata.keys():
            if metadata[key] == '':
                del metadata[key]
        session['metadata'] = metadata
        print cnxml
        session['cnxml'] = cnxml
        return HTTPFound(location=request.route_url('importer'))
    response = {
        'form': FormRenderer(form),
        'presentationform': FormRenderer(presentationform),
        'field_list': field_list,
    }
    return render_to_response(templatePath, response, request=request)


class PreviewSchema(formencode.Schema):
    allow_extra_fields = True
    title = formencode.validators.String()


@view_config(route_name='preview', renderer='templates/preview.pt',
    http_cache=(0, {'no-store': True, 'no-cache': True, 'must-revalidate': True}))
def preview_view(request):
    check_login(request)
    session = request.session
    module = request.params.get('module')
    if module:
        conn = sword2cnx.Connection(session['service_document_url'],
                                    user_name=session['username'],
                                    user_pass=session['password'],
                                    always_authenticate=True,
                                    download_service_document=False)

        # example: http://cnx.org/Members/user001/m17222/sword/editmedia
        result = conn.get_resource(content_iri = module,
                                   packaging = ZIP_PACKAGING) 
        
    defaults = {}
    defaults['title'] = request.session.get('title', '')
    form = Form(request,
                schema=PreviewSchema,
                defaults=defaults
               )

    body_filename = request.session.get('preview-no-cache')
    if body_filename is None:
        body_filename = 'index.html'
    else:
        del request.session['preview-no-cache']

    return {
        'body_base': '%s%s/' % (
                     request.static_url('oerpub.rhaptoslabs.swordpushweb:transforms/'),
                     request.session['upload_dir']),
        'body_url': '%s%s/index.html'% (
                     request.static_url('oerpub.rhaptoslabs.swordpushweb:transforms/'),
                     request.session['upload_dir']),
        'form': FormRenderer(form),
        'editor': EditorHelper(request)
    }


@view_config(route_name='preview_save')
def preview_save(request):
    check_login(request)
    html = request.POST['html']
    if isinstance(html, unicode):
        html = html.encode('ascii', 'xmlcharrefreplace')        

    save_dir = os.path.join(request.registry.settings['transform_dir'],
        request.session['upload_dir'])
    # Save new html file from preview area
    save_and_backup_file(save_dir, 'index.html', html)

    conversionerror = ''

    #transform preview html to cnxml
    cnxml = None
    try:
        structured_html = aloha_to_html(html)           #1 create structured HTML5
        cnxml = html_to_valid_cnxml(structured_html)    #2 create cnxml from structured HTML5

        # parse the new title from structured HTML
        tree = etree.fromstring(structured_html, etree.HTMLParser())
        try:
            edited_title = tree.xpath('/html/head/title/text()')[0]
            request.session['title'] = edited_title
        except:
            request.session['title'] = 'Untitled Document'
    except Exception as e:
        #return render_conversionerror(request, str(e))
        conversionerror = str(e)

    if cnxml is not None:
        try:
            validate_cnxml(cnxml)
        except ConversionError as e:
            #return render_conversionerror(request, str(e))
            conversionerror = str(e)
        else:
            save_and_backup_file(save_dir, 'index.cnxml', cnxml)
            files = get_files_from_zipfile(os.path.join(save_dir, 'upload.zip'))
            save_zip(save_dir, cnxml, html, files)

    response = Response(json.dumps({'saved': True, 'error': conversionerror}))
    response.content_type = 'application/json'
    return response

class CnxmlSchema(formencode.Schema):
    allow_extra_fields = True
    cnxml = formencode.validators.String(not_empty=True)

@view_config(route_name='cnxml', renderer='templates/cnxml_editor.pt')
def cnxml_view(request):
    check_login(request)
    form = Form(request, schema=CnxmlSchema)
    save_dir = os.path.join(request.registry.settings['transform_dir'], request.session['upload_dir'])
    cnxml_filename = os.path.join(save_dir, 'index.cnxml')
    transformerror = request.session.get('transformerror')

    # Check for successful form completion
    if 'cnxml' in request.POST and form.validate():
        cnxml = form.data['cnxml']
        
        # Keep sure we use the standard python ascii string and encode Unicode to xml character mappings
        if isinstance(cnxml, unicode):
            cnxml = cnxml.encode('ascii', 'xmlcharrefreplace')        


        try:
            files = get_files_from_zipfile(os.path.join(save_dir, 'upload.zip'))
            save_cnxml(save_dir, cnxml, files)
            validate_cnxml(cnxml)
        except ConversionError as e:
            return render_conversionerror(request, e.msg)

        # Return to preview
        return HTTPFound(location=request.route_url('preview'), request=request)

    # Read CNXML
    with open(cnxml_filename, 'rt') as fp:
        cnxml = fp.read()

    # Clean CNXML
    cnxml = clean_cnxml(cnxml)
    cnxml = cnxml.decode('utf-8')
    cnxml = unicode(cnxml)

    return {
        'codemirror': True,
        'form': FormRenderer(form),
        'cnxml': cnxml,
        'transformerror': transformerror,
    }


@view_config(route_name='summary')
def summary_view(request):
    check_login(request)
    templatePath = 'templates/summary.pt'
    import parse_sword_treatment

    deposit_receipt = request.session['deposit_receipt']
    response = parse_sword_treatment.get_requirements(deposit_receipt)
    return render_to_response(templatePath, response, request=request)


class ConfigSchema(formencode.Schema):
    allow_extra_fields = True
    service_document_url = formencode.validators.URL(add_http=True)
    workspace_url = formencode.validators.URL(add_http=True)
    title = formencode.validators.String()
    summary = formencode.validators.String()
    subject = formencode.validators.Set()
    keywords = formencode.validators.String()
    language = formencode.validators.String(not_empty=True)
    google_code = formencode.validators.String()
    authors = formencode.validators.String()
    maintainers = formencode.validators.String()
    copyright = formencode.validators.String()
    editors = formencode.validators.String()
    translators = formencode.validators.String()


@view_config(route_name='admin_config', renderer='templates/admin_config.pt')
def admin_config_view(request):
    """
    Configure default UI parameter settings
    """

    check_login(request)
    subjects = ["Arts", "Business", "Humanities", "Mathematics and Statistics",
                "Science and Technology", "Social Sciences"]
    form = Form(request, schema=ConfigSchema)
    config = load_config(request)

    # Check for successful form completion
    if 'form.submitted' in request.POST:
        form.validate()
        for key in ['service_document_url', 'workspace_url']:
            config[key] = form.data[key]
        for key in ['title', 'summary', 'subject', 'keywords', 'language', 'google_code']:
            config['metadata'][key] = form.data[key]
        for key in ['authors', 'maintainers', 'copyright', 'editors', 'translators']:
            config['metadata'][key] = [x.strip() for x in form.data[key].split(',')]
        save_config(config, request)

    response =  {
        'form': FormRenderer(form),
        'subjects': subjects,
        'languages': languages,
        'roles': [('authors', 'Authors'),
                  ('maintainers', 'Maintainers'),
                  ('copyright', 'Copyright holders'),
                  ('editors', 'Editors'),
                  ('translators',
                  'Translators')
                 ],
        'request': request,
        'config': config,
    }
    return response


def get_module_list(connection, workspace):
    xml = sword2cnx.get_module_list(connection, workspace)
    tree = lxml.etree.XML(xml)
    ns_dict = {'xmlns:sword': 'http://purl.org/net/sword/terms/',
               'xmlns': 'http://www.w3.org/2005/Atom'}
    elements =  tree.xpath('/xmlns:feed/xmlns:entry', namespaces=ns_dict)

    modules = []
    for element in elements:
        title_element = element.xpath('./xmlns:title', namespaces=ns_dict)[0]
        title = title_element.text

        link_elements = element.xpath('./xmlns:link[@rel="edit"]',
                                      namespaces=ns_dict
                                     )
        edit_link = link_elements[0].get('href')

        path_elements = edit_link.split('/')
        view_link = '/'.join(path_elements[:-1])
        path_elements.reverse()
        uid = path_elements[1]

        modules.append([uid, edit_link, title, view_link])
    return modules


class MetadataSchema(formencode.Schema):
    allow_extra_fields = True
    title = formencode.validators.String(not_empty=True)
    keep_title = formencode.validators.Bool()
    summary = formencode.validators.String()
    keep_summary = formencode.validators.Bool()
    keywords = formencode.validators.String()
    keep_keywords = formencode.validators.Bool()
    subject = formencode.validators.Set()
    keep_subject = formencode.validators.Bool()
    language = formencode.validators.String(not_empty=True)
    keep_language = formencode.validators.Bool()
    google_code = formencode.validators.String()
    keep_google_code = formencode.validators.Bool()
    workspace = formencode.validators.String(not_empty=True)
    keep_workspace = formencode.validators.Bool()
    authors = formencode.validators.String(not_empty=True)
    maintainers = formencode.validators.String(not_empty=True)
    copyright = formencode.validators.String(not_empty=True)
    editors = formencode.validators.String()
    translators = formencode.validators.String()


class Metadata_View(BaseHelper):
    
    def __init__(self, request):
        super(Metadata_View, self).__init__(request)
        self.check_login()
        self.templatePath = 'templates/metadata.pt'
        self.config = load_config(request)
        self.metadata = self.config['metadata']
        self.featured_links = []
        self.workspaces = \
            [(i['href'], i['title']) for i in self.session['collections']]

        self.role_mappings = {'authors': 'dcterms:creator',
                              'maintainers': 'oerdc:maintainer',
                              'copyright': 'dcterms:rightsHolder',
                              'editors': 'oerdc:editor',
                              'translators': 'oerdc:translator'}

        self.subjects = ["Arts",
                         "Business",
                         "Humanities",
                         "Mathematics and Statistics",
                         "Science and Technology",
                         "Social Sciences",
                         ]

        # The roles fields are comma-separated strings. This makes the javascript
        # easier on the client side, and is easy to parse. The fields are hidden,
        # and the values will be user ids, which should not have commas in them.
        self.field_list = [
            ['authors', 'authors', {'type': 'hidden'}],
            ['maintainers', 'maintainers', {'type': 'hidden'}],
            ['copyright', 'copyright', {'type': 'hidden'}],
            ['editors', 'editors', {'type': 'hidden'}],
            ['translators', 'translators', {'type': 'hidden'}],
            ['title', 'Title', {'type': 'text'}],
            ['summary', 'Summary', {'type': 'textarea'}],
            ['keywords', 'Keywords (One per line)', {'type': 'textarea'}],
            ['subject', 'Subject', {'type': 'checkbox',
                                    'values': self.subjects}],
            ['language', 'Language', {'type': 'select',
                                      'values': languages,
                                      'selected_value': 'en'}],
            ['google_code', 'Google Analytics Code', {'type': 'text'}],
            ['workspace', 'Workspace', {'type': 'select',
                                      'values': self.workspaces}],
        ]

        self.remember_fields = [field[0] for field in self.field_list[5:]]

        # Get remembered fields from the session
        self.defaults = {}

        # Get remembered title from the session    
        if 'title' in self.session:
            self.defaults['title'] = self.session['title']
            self.config['metadata']['title'] = self.session['title']

    def update_session(self, session, remember_fields, form):        
        # Persist the values that should be persisted in the session, and
        # delete the others.
        for field_name in remember_fields:
            if form.data['keep_%s' % field_name]:
                session[field_name] = form.data[field_name]
            else:
                if field_name in session:
                    del(session[field_name])
        return session
    
    def get_metadata_entry(self, form, session):
        metadata = {}
        metadata['dcterms:title'] = form.data['title'] if form.data['title'] \
                                    else session['filename']

        # Summary
        metadata['dcterms:abstract'] = form.data['summary'].strip()

        # Language
        metadata['dcterms:language'] = form.data['language']

        # Subjects
        metadata['oerdc:oer-subject'] = form.data['subject']

        # Keywords
        metadata['dcterms:subject'] = [i.strip() for i in
                                       form.data['keywords'].splitlines()
                                       if i.strip()]

        # Google Analytics code
        metadata['oerdc:analyticsCode'] = form.data['google_code'].strip()

        # Standard change description
        metadata['oerdc:descriptionOfChanges'] = 'Uploaded from external document importer.'

        # Build metadata entry object
        for key in metadata.keys():
            if metadata[key] == '':
                del metadata[key]
        metadata_entry = sword2cnx.MetaData(metadata)

        # Add role tags
        role_metadata = {}
        for k, v in self.role_mappings.items():
            role_metadata[v] = form.data[k].split(',')
        for key, value in role_metadata.iteritems():
            for v in value:
                v = v.strip()
                if v:
                    metadata_entry.add_field(key, '', {'oerdc:id': v})

        return metadata_entry 

    def get_raw_featured_links(self, request):
        data = peppercorn.parse(request.POST.items())
        if data is None or len(data.get('featuredlinks')) < 1:
            return []

        # get featured links from data
        tmp_links = {}
        # first we organise the links by category
        for details in data['featuredlinks']:
            category = details['fl_category']
            tmp_list = tmp_links.get(category, [])
            tmp_list.append(details)
            tmp_links[category] = tmp_list
        return tmp_list

    def add_featured_links(self, request, zip_file, save_dir):
        structure = peppercorn.parse(request.POST.items())
        if structure.has_key('featuredlinks'):
            featuredlinks = build_featured_links(structure)
            if featuredlinks:
                cnxml = get_cnxml_from_zipfile(zip_file)
                new_cnxml = add_featuredlinks_to_cnxml(cnxml,
                                                       featuredlinks)
                files = get_files_from_zipfile(zip_file)
                save_cnxml(save_dir, new_cnxml, files)
        return featuredlinks

    def create_module_with_atompub_xml(self, conn, collection_iri, entry):
        dr = conn.create(col_iri = collection_iri,
                         metadata_entry = entry,
                         in_progress = True)
        return dr

    def update_module(self, save_dir, connection, metadata, module_url):
        zip_file = open(os.path.join(save_dir, 'upload.zip'), 'rb')
        deposit_receipt = connection.update(
            metadata_entry = metadata,
            payload = zip_file,
            filename = 'upload.zip',
            mimetype = 'application/zip',
            packaging = ZIP_PACKAGING,
            edit_iri = module_url,
            edit_media_iri = module_url + '/editmedia',
            metadata_relevant=False,
            in_progress=True)
        zip_file.close()
        return deposit_receipt

    def create_module(self, form, connection, metadata, zip_file): 
        deposit_receipt = connection.create(
            col_iri = form.data['workspace'],
            metadata_entry = metadata,
            payload = zip_file,
            filename = 'upload.zip',
            mimetype = 'application/zip',
            packaging = ZIP_PACKAGING,
            in_progress = True)
        return deposit_receipt

    @reify
    def workspace_popup(self):
        return self.macro_renderer.implementation().macros['workspace_popup']

    @reify
    def featured_link(self):
        return self.macro_renderer.implementation().macros['featured_link']

    @reify
    def featured_links_table(self):
        return self.macro_renderer.implementation().macros['featured_links_table']

    def show_featured_links_form(self):
        return self.metadata.get('featured_link_groups', '') and 'checked' or ''

    def get_title(self, metadata, session):
        return metadata.get('dcterms:title', session.get('title', ''))

    def get_subjects(self, metadata):
        return metadata.get('subjects', [])

    def get_summary(self, metadata):
        return metadata.get('dcterms:abstract', '')
    
    def get_values(self, field):
        return getattr(self, field)

    @reify
    def get_featured_link_groups(self):
        return self.metadata.get('featured_link_groups', [])

    @reify
    def authors(self):
        return self.get_contributors('dcterms:creator', self.metadata)

    @reify
    def maintainers(self):
        return self.get_contributors('oerdc:maintainer', self.metadata)

    @reify
    def copyright(self):
        return self.get_contributors('dcterms:rightsHolder', self.metadata)

    @reify
    def editors(self):
        return self.get_contributors('oerdc:editor', self.metadata)

    @reify
    def translators(self):
        return self.get_contributors('oerdc:translator', self.metadata)
    
    def get_contributors(self, role, metadata):
        delimeter = ','
        default = self.get_default(role)
        val = metadata.get(role, default)
        if isinstance(val, types.ListType):
            val = delimeter.join(val)
        return val

    def get_default(self, role):
        for k, v in self.role_mappings.items():
            if v == role:
                break
        return self.defaults.get(k, [])

    def get_language(self, metadata):
        default = self.defaults.get('language')
        return metadata.get('dcterms:language', default)

    def get_keywords(self, metadata):
        delimeter = '\n'
        val = metadata.get('keywords', '')
        if isinstance(val, types.ListType):
            val = delimeter.join(val) 
        return val

    def get_google_code(self, metadata):
        return metadata.get('oerdc:analyticsCode', '')

    def get_strength_image_name(self, link):
        return 'strength%s.png' % link.strength

    @view_config(route_name='metadata')
    def generate_html_view(self):
        """
        Handle metadata adding and uploads
        """
        session = self.session
        request = self.request
        config = self.config
        workspaces = self.workspaces
        subjects = self.subjects
        field_list = self.field_list
        remember_fields = self.remember_fields
        defaults = self.defaults

        form = Form(request,
                    schema=MetadataSchema,
                    defaults=defaults
                   )

        # Check for successful form completion
        if form.validate():
            self.update_session(session, remember_fields, form)

            # Reconstruct the path to the saved files
            save_dir = os.path.join(
                request.registry.settings['transform_dir'],
                session['upload_dir']
            )

            # Create a connection to the sword service
            conn = self.get_connection()

            # Send zip file to Connexions through SWORD interface
            with open(os.path.join(save_dir, 'upload.zip'), 'rb') as zip_file:
                # Create the metadata entry
                metadata_entry = self.get_metadata_entry(form, session)
                self.featured_links = self.add_featured_links(request,
                                                              zip_file,
                                                              save_dir)

                associated_module_url = request.POST.get('associated_module_url')
                if associated_module_url:
                    # this is an update not a create
                    deposit_receipt = self.update_module(
                        save_dir, conn, metadata_entry, associated_module_url)
                else:
                    # this is a workaround until I can determine why the 
                    # featured links don't upload correcly with a multipart
                    # upload during module creation. See redmine issue 40
                    # TODO:
                    # Fix me properly!
                    if self.featured_links:
                        deposit_receipt = create_module_in_2_steps(
                            form, conn, metadata_entry, zip_file, save_dir)
                    else:
                        deposit_receipt = self.create_module(
                            form, conn, metadata_entry, zip_file)

            # Remember to which workspace we submitted
            session['deposit_workspace'] = workspaces[[x[0] for x in workspaces].index(form.data['workspace'])][1]

            # The deposit receipt cannot be pickled, so we pickle the xml
            session['deposit_receipt'] = deposit_receipt.to_xml()

            # Go to the upload page
            return HTTPFound(location=request.route_url('summary'))

        module_url = request.POST.get('module', None)
        metadata = config['metadata']
        username = self.session['username']
        password = self.session['password']
        if module_url:
            metadata.update(get_metadata_from_repo(session, module_url, username, password))
        else:
            for role in ['authors', 'maintainers', 'copyright', 'editors', 'translators']:
                self.defaults[role] = ','.join(
                    self.config['metadata'][role]).replace('_USER_', username)

                self.config['metadata'][role] = ', '.join(
                    self.config['metadata'][role]).replace('_USER_', username)
                
                self.defaults['language'] = \
                    self.config['metadata'].get('language', u'en')

        selected_workspace = request.POST.get('workspace', None)
        selected_workspace = selected_workspace or workspaces[0][0]
        workspace_title = [w[1] for w in workspaces if w[0] == selected_workspace][0]
        response =  {
            'form': FormRenderer(form),
            'field_list': field_list,
            'workspaces': workspaces,
            'selected_workspace': selected_workspace,
            'workspace_title': workspace_title,
            'module_url': module_url,
            'languages': languages,
            'subjects': subjects,
            'config': config,
            'macros': self.macro_renderer,
            'metadata': metadata,
            'session': session,
            'view': self,
        }
        return render_to_response(self.templatePath, response, request=request)

class ModuleAssociationSchema(formencode.Schema):
    allow_extra_fields = True
    module = formencode.validators.String()


class Module_Association_View(BaseHelper):

    @view_config(route_name='module_association',
                 renderer='templates/module_association.pt')
    def generate_html_view(self):
        request = self.request

        self.check_login()
        config = load_config(request)
        conn = self.get_connection()

        workspaces = [
            (i['href'], i['title']) for i in self.session['collections']
        ]
        selected_workspace = request.params.get('workspace', workspaces[0][0])
        workspace_title = [w[1] for w in workspaces if w[0] == selected_workspace][0]

        b_start = int(request.GET.get('b_start', '0'))
        b_size = int(request.GET.get('b_size', config.get('default_batch_size')))

        modules = get_module_list(conn, selected_workspace)
        modules = Batch(modules, start=b_start, size=b_size)
        module_macros = get_renderer('templates/modules_list.pt').implementation()

        form = Form(request, schema=ModuleAssociationSchema)
        response = {'form': FormRenderer(form),
                    'workspaces': workspaces,
                    'selected_workspace': selected_workspace,
                    'workspace_title': workspace_title,
                    'modules': modules,
                    'request': request,
                    'config': config,
                    'module_macros': module_macros,
        }
        return response

    @reify
    def macros(self):
        return self.macro_renderer.implementation().macros

    @reify
    def workspace_list(self):
        return self.macro_renderer.implementation().macros['workspace_list']

    @reify
    def workspace_popup(self):
        return self.macro_renderer.implementation().macros['workspace_popup']

    @reify
    def modules_list(self):
        return self.macro_renderer.implementation().macros['modules_list']


class Modules_List_View(BaseHelper):

    @view_config(
        route_name='modules_list', renderer="templates/modules_list.pt")
    def generate_html_view(self):
        check_login(self.request)
        config = load_config(self.request)
        conn = self.get_connection()

        selected_workspace = self.session['collections'][0]['href']
        selected_workspace = self.request.params.get('workspace',
                                                     selected_workspace)
        print "Workspace url: " + selected_workspace

        modules = get_module_list(conn, selected_workspace)
        b_start = int(self.request.GET.get('b_start', '0'))
        b_size = int(self.request.GET.get('b_size', 
                                          config.get('default_batch_size')))
        modules = Batch(modules, start=b_start, size=b_size)

        response = {'selected_workspace': selected_workspace,
                    'modules': modules,
                    'request': self.request,
                    'config': config,
        }
        return response

    @reify
    def modules_list(self):
        return self.macro_renderer.implementation().macros['modules_list']


class Choose_Module(Module_Association_View):

    @view_config(
        route_name='choose-module', renderer="templates/choose_module.pt")
    def generate_html_view(self):
        return super(Choose_Module, self).generate_html_view()

    @reify
    def content_macro(self):
        return self.macro_renderer.implementation().macros['content_macro']
        
@view_config(route_name='download_zip',
    http_cache=(0, {'no-store': True, 'no-cache': True, 'must-revalidate': True}))
def download_zip(request):
    check_login(request)

    res = Response(content_type='application/zip')
    res.headers.add('Content-Disposition', 'attachment;filename=saved-module.zip')

    save_dir = os.path.join(request.registry.settings['transform_dir'],
        request.session['upload_dir'])
    zipfile = open(os.path.join(save_dir, 'upload.zip'), 'rb')
    stat = os.fstat(zipfile.fileno())
    res.app_iter = iter(lambda: zipfile.read(4096), '')
    res.content_length = stat.st_size
    res.last_modified = datetime.datetime.utcfromtimestamp(
        stat.st_mtime).strftime('%a, %d %b %Y %H:%M:%S GMT')
    return res

@view_config(route_name='upload_dnd')
def upload_dnd(request):
    check_login(request)

    save_dir = os.path.join(request.registry.settings['transform_dir'],
        request.session['upload_dir'])

    # userfn, if browser does not support naming of blobs, this might be
    # 'blob', so we need to further uniquefy it.
    userfn = request.POST['upload'].filename or ''
    ext = ''
    mtype = request.POST['upload'].headers.get('content-type')
    if mtype is not None:
        ext = mimetypes.guess_extension(mtype) or ''

    # If it has an extension (a dot and three of four characters at the end),
    # strip it
    userfn = re.compile('\.\w{3,4}$').sub('', userfn)
    fn = userfn + '_' + datetime.datetime.now().strftime('%s') + ext

    # No point in using an iterator, we need the entire content for the zip
    # file anyway
    fob = request.POST['upload'].file
    blk = fob.read()
    with open(os.path.join(save_dir, fn), 'w') as fp:
        fp.write(blk)

    # Update upload.zip
    append_zip(os.path.join(save_dir, 'upload.zip'), fn, blk)

    response = Response(json.dumps({'url': fn}))
    response.content_type = 'application/json'
    return response

@view_config(name='toolbar', renderer='templates/toolbar.pt')
def toolbar(request):
    return {}

        
def get_oauth_token_and_secret(username):
    try:
        connection = mdb.connect('localhost', 'root',  'fedora', 'cnx_oerpub_oauth');
        with connection:
            cursor = connection.cursor()
            cursor.execute("SELECT oauth_token,oauth_secret FROM user WHERE username='"+username+"'")
            row = cursor.fetchone()
            return {"oauth_token": row[0],"oauth_secret":row[1]}
    except mdb.Error, e:
        print e

def is_returning_google_user(username):
    connection = mdb.connect('localhost', 'root', 'fedora', 'cnx_oerpub_oauth')
    query = "SELECT * FROM user WHERE username='"+username+"'"
    print query
    numrows=0
    with connection:
        cursor = connection.cursor()
        cursor.execute(query)
        numrows = int(cursor.rowcount)
    connection.close()
    if numrows == 0:
        return False
    else :
        return True


@view_config(route_name='importer',renderer='templates/importer.pt')
def return_slideshare_upload_form(request):
    check_login(request)
    session = request.session
    redirect_to_google_oauth = False
    if session.has_key('original-file-location'):
        del session['original-file-location']
    form = Form(request, schema=ImporterChoiceSchema)
    response = {'form':FormRenderer(form)}
    validate_form = form.validate()
    if validate_form:
        original_filename = session['original_filename']
        upload_to_google = form.data['upload_to_google']
        upload_to_ss = form.data['upload_to_ss']
        username = session['username']
        if (upload_to_ss=="true"):

            slideshow_id = upload_to_slideshare("saketkc",original_filename)
            session['slideshare_id'] = slideshow_id
        if (upload_to_google == "true"):
            if is_returning_google_user(username):
                print "RETURNING USER"
                redirect_to_google_oauth = False
                oauth_token_and_secret = get_oauth_token_and_secret(username)
                oauth_token = oauth_token_and_secret["oauth_token"]
                oauth_secret = oauth_token_and_secret["oauth_secret"]
                guploader = GooglePresentationUploader()
                guploader.authentincate_client_with_oauth2(oauth_token,oauth_secret)
                guploader.upload(original_filename)
                guploader.get_first_revision_feed()
                guploader.publish_presentation_on_web()
                resource_id = guploader.get_resource_id().split(':')[1]
                session['google-resource-id'] = resource_id
                print "UPLOADING TO GOOGLE"
            else:
                print "NEW USER"
                redirect_to_google_oauth = True
                session['original-file-path'] = original_filename
        else:
            print "NO GOOGLE FOUND"
        username = session['username']
        uploaded_filename = session['uploaded_filename']
        slideshare_details = get_details(slideshow_id)
        slideshare_download_url = get_slideshow_download_url(slideshare_details)
        session['transcript'] = get_transcript(slideshare_details)
        cnxml = """<featured-links>
  <!-- WARNING! The 'featured-links' section is read only. Do not edit below.
       Changes to the links section in the source will not be saved. -->
    <link-group type="supplemental">
      <link url="""+ "\"" + uploaded_filename + "\""+""" strength="3">Download the original slides in PPT format</link>
      <link url="""+ "\"" +slideshare_download_url + "\"" +""" strength="2">SlideShare PPT Download Link</link>
    </link-group>
  <!-- WARNING! The 'featured-links' section is read only. Do not edit above.
       Changes to the links section in the source will not be saved. -->
</featured-links>"""
        session['cnxml'] += cnxml



        #print deposit_receipt.metadata #.get("dcterms_title")
        if redirect_to_google_oauth:
            raise HTTPFound(location=request.route_url('google_oauth'))
        raise HTTPFound(location=request.route_url('enhance'))
    return {'form' : FormRenderer(form),'conversion_flag': False, 'oembed': False}

@view_config(route_name='oauth2callback')
def google_oauth_callback(request):
    url = request.host_url + request.path_qs
    url =  url.replace('%2F','/')
    if not request.session.has_key('saved_request_token'):
        return HTTPFound(location = '/google_oauth')
    oauth = GoogleOAuth(request_token = request.session['saved_request_token'])
    oauth.authorize_request_token(request.session['saved_request_token'],url)
    oauth.get_access_token()
    session = request.session
    connection = mdb.connect('localhost', 'root',  'fedora', 'cnx_oerpub_oauth');
    oauth_token =  oauth.get_token_key()
    oauth_secret = oauth.get_token_secret()
    query = "INSERT INTO user(username,email,oauth_token,oauth_secret) VALUES("+"'"+session['username']+"'"+","+"'test@gmail.com'"+","+"'"+oauth_token+"'"+","+"'"+oauth_secret+"'"+")"
    with connection:
        cursor = connection.cursor()
        cursor.execute(query)
    connection.close()
    guploader = GooglePresentationUploader()
    guploader.authentincate_client_with_oauth2(oauth_token,oauth_secret)
    upload_to_gdocs = guploader.upload(session['original-file-path'])
    guploader.get_first_revision_feed()
    guploader.publish_presentation_on_web()
    resource_id = guploader.get_resource_id().split(':')[1]
    session['google-resource-id'] = resource_id
    if session.has_key('original-file-location'):
        del session['original-file-location']
    raise HTTPFound(location=request.route_url('enhance'))


@view_config(route_name='updatecnx')
def update_cnx_metadata(request):
    """
    Handle update of metadata to cnx
    """
    check_login(request)
    templatePath = 'templates/update_metadata.pt'
    session = request.session
    config = load_config(request)
    workspaces = [(i['href'], i['title']) for i in session['collections']]
    subjects = ["Arts",
                "Business",
                "Humanities",
                "Mathematics and Statistics",
                "Science and Technology",
                "Social Sciences",
                ]
    field_list = [
                  ['authors', 'authors', {'type': 'hidden'}],
                  ['maintainers', 'maintainers', {'type': 'hidden'}],
                  ['copyright', 'copyright', {'type': 'hidden'}],
                  ['editors', 'editors', {'type': 'hidden'}],
                  ['translators', 'translators', {'type': 'hidden'}],
                  ['title', 'Title', {'type': 'text'}],
                  ['summary', 'Summary', {'type': 'textarea'}],
                  ['keywords', 'Keywords (One per line)', {'type': 'textarea'}],
                  ['subject', 'Subject', {'type': 'checkbox',
                                          'values': subjects}],
                  ['language', 'Language', {'type': 'select',
                                            'values': languages,
                                            'selected_value': 'en'}],
                  ['google_code', 'Google Analytics Code', {'type': 'text'}],
                  ['workspace', 'Workspace', {'type': 'select',
                                            'values': workspaces}],
                  ]
    remember_fields = [field[0] for field in field_list[5:]]
    defaults = {}

    for role in ['authors', 'maintainers', 'copyright', 'editors', 'translators']:
        defaults[role] = ','.join(config['metadata'][role]).replace('_USER_', session['username'])
        config['metadata'][role] = ', '.join(config['metadata'][role]).replace('_USER_', session['username'])

    if 'title' in session:
        print('TITLE '+session['title']+' in session')
        defaults['title'] = session['title']
        config['metadata']['title'] = session['title']

    form = Form(request,
                schema=MetadataSchema,
                defaults=defaults
                )

    # Check for successful form completion
    if form.validate():
        for field_name in remember_fields:
            if form.data['keep_%s' % field_name]:
                session[field_name] = form.data[field_name]
            else:
                if field_name in session:
                    del(session[field_name])

        metadata = {}
        metadata['dcterms:title'] = form.data['title'] if form.data['title'] \
                                    else session['filename']
        metadata_entry = sword2cnx.MetaData(metadata)
        role_metadata = {}
        role_mappings = {'authors': 'dcterms:creator',
                         'maintainers': 'oerdc:maintainer',
                         'copyright': 'dcterms:rightsHolder',
                         'editors': 'oerdc:editor',
                         'translators': 'oerdc:translator'}
        for k, v in role_mappings.items():
            role_metadata[v] = form.data[k].split(',')
        for key, value in role_metadata.iteritems():
            for v in value:
                v = v.strip()
                if v:
                    metadata_entry.add_field(key, '', {'oerdc:id': v})
        conn = sword2cnx.Connection("http://cnx.org/sword/servicedocument",
                                    user_name=session['username'],
                                    user_pass=session['password'],
                                    always_authenticate=True,
                                    download_service_document=True)
        update = conn.update(edit_iri=session['edit_iri'],metadata_entry = metadata_entry,in_progress=True,metadata_relevant=True)
        metadata={}
        metadata['dcterms:title'] = form.data['title'] if form.data['title'] \
                                    else session['filename']
        metadata['dcterms:abstract'] = form.data['summary'].strip()
        metadata['dcterms:language'] = form.data['language']
        metadata['dcterms:subject'] = [i.strip() for i in
                                       form.data['keywords'].splitlines()
                                       if i.strip()]
        metadata['oerdc:oer-subject'] = form.data['subject']
        for key in metadata.keys():
            if metadata[key] == '':
                del metadata[key]
        add = conn.update_metadata_for_resource(edit_iri=session['edit_iri'],metadata_entry = metadata_entry,in_progress=True)
        metadata['oerdc:analyticsCode'] = form.data['google_code'].strip()
        for key in metadata.keys():
            if metadata[key] == '':
                del metadata[key]
        metadata_entry = sword2cnx.MetaData(metadata)
        add = conn.update(edit_iri=session['edit_iri'],metadata_entry = metadata_entry,in_progress=True)
        return HTTPFound(location=request.route_url('summary'))
    response =  {
        'form': FormRenderer(form),
        'field_list': field_list,
        'workspaces': workspaces,
        'languages': languages,
        'subjects': subjects,
        'config': config,
    }
    return render_to_response(templatePath, response, request=request)

@view_config(route_name='enhance')
def enhance(request):
    check_login(request)
    session = request.session
    google_resource_id = ""
    slideshare_id = ""
    embed_google = False
    embed_slideshare = False
    not_converted = True
    show_iframe = False
    form = Form(request, schema=QuestionAnswerSchema)
    validate_form = form.validate()
    print form.all_errors()
    if session.has_key('google-resource-id'):
        google_resource_id = session['google-resource-id']
    if session.has_key('slideshare_id'):
        slideshare_id = session['slideshare_id']
        if fetch_slideshow_status(slideshare_id) == "2":
            not_converted = False
            show_iframe = True



    if google_resource_id!="":
        embed_google = True
    if slideshare_id!="":
        embed_slideshare = True
    templatePath = "templates/google_ss_preview.pt"
    if validate_form:
        introductory_paragraphs = request.POST.get('introductory_paragraphs')
        question_count=0
        cnxml=session["cnxml"]+"""<content><section id="intro-section-title"><title id="introtitle">Introduction</title><para id="introduction-1">"""+introductory_paragraphs+"""</para></section><section id="slides-embed"><title id="slide-embed-title">View the slides</title><figure id="ss-embed-figure"><media id="slideshare-embed" alt="slideshare-embed"><iframe src="http://www.slideshare.net/slideshow/embed_code/"""+slideshare_id+"""" width="425" height="355" /></media></figure></section>"""        
        for i in range(1,6):
            form_question = request.POST.get('question-'+str(i))
            if form_question:                
                form_radio_answer = request.POST.get('radio-'+str(i)) #this give us something like 'answer-1-1'. so our solution is this
                question_count +=1                
                if question_count==1:
					cnxml+="""<section id="test-section"><title>Test your knowledge</title>"""
                itemlist = ""
                for j in range(1,10):
                    try:
                        
                        form_all_answers = request.POST.get('answer-'+str(i)+'-'+str(j))
                        if form_all_answers:
                            itemlist +="<item>" + form_all_answers+"</item>"
                        
                    except:
                        print "No element found"
                
                if form_radio_answer:
					solution = request.POST.get(form_radio_answer)
					cnxml+="""<exercise id="exercise-"""+str(i)+""""><problem id="problem-"""+str(i)+""""><para id="para-"""+str(i)+"""">"""+str(form_question)+"""<list id="option-list-"""+str(i)+"""" list-type="enumerated" number-style="lower-alpha">"""+str(itemlist)+"""</list></para></problem>"""
                else:
                    print "ELESE CONDUITION OF radio"
                    solution = request.POST.get('answer-'+str(i)+'-1')
                    cnxml+="""<exercise id="exercise-"""+str(i)+""""><problem id="problem-"""+str(i)+""""><para id="para-"""+str(i)+"""">"""+str(form_question)+"""</para></problem>"""
                print "FORM RADIO ANSWER",form_radio_answer
                print "SOLUTION", solution                
                cnxml+=""" <solution id="solution-"""+str(i)+""""> <para id="solution-para-"""+str(i)+"""">"""+solution+"""</para></solution></exercise>"""
				
					
                """form_solution = request.POST.get('solution-'+str(i))
                all_post_data = {"data":{"options":form_options,"solution":form_solution,"question":form_question}}
                for question in all_post_data:
                    options = all_post_data[question]['options']
                    solution = all_post_data[question]['solution']
                    asked_question = all_post_data[question]['question']
                    optionlist=""
                    for option in options:
                        optionlist+="<item>"+option+"</item>"""
                    #cnxml+="""<exercise id="exercise-"""+str(j)+""""><problem id="problem-"""+str(j)+""""><para id="para-"""+str(j)+"""">"""+str(asked_question)+"""<list id="option-list-"""+str(j)+"""" list-type="enumerated" number-style="lower-alpha">"""+str(optionlist)+"""</list></para></problem>"""
                    #cnxml+=""" <solution id="solution-"""+str(j)+""""> <para id="solution-para-"""+str(j)+"""">"""+solution+"""</para></solution></exercise>"""
                    #j+=1
        metadata = session['metadata']
        if question_count>=1:
			cnxml += "</section></content></document>"
        else:
            cnxml += "</content></document>"
        workspaces = [(i['href'], i['title']) for i in session['collections']]
        metadata_entry = sword2cnx.MetaData(metadata)
        zipped_filepath = session['userfilepath']
        zip_archive = zipfile.ZipFile(zipped_filepath, 'w')
        zip_archive.writestr("index.cnxml",cnxml)
        zip_archive.close()
        conn = sword2cnx.Connection("http://cnx.org/sword/servicedocument",
                                    user_name=session['username'],
                                    user_pass=session['password'],
                                    always_authenticate=True,
                                    download_service_document=True)
        collections = [{'title': i.title, 'href': i.href}
                                  for i in sword2cnx.get_workspaces(conn)]
        session['collections'] = collections
        workspaces = [(i['href'], i['title']) for i in session['collections']]
        session['workspaces'] = workspaces
        with open(zipped_filepath, 'rb') as zip_file:
            deposit_receipt = conn.create(
                col_iri = workspaces[0][0],
                metadata_entry = metadata_entry,
                payload = zip_file,
                filename = 'upload.zip',
                mimetype = 'application/zip',
                packaging = 'http://purl.org/net/sword/package/SimpleZip',
                in_progress = True)
        session['dr'] = deposit_receipt
        session['deposit_receipt'] = deposit_receipt.to_xml()
        soup = BeautifulSoup(deposit_receipt.to_xml())
        data = soup.find("link",rel="edit")
        edit_iri = data['href']
        session['edit_iri'] = edit_iri
        creator = soup.find('dcterms:creator')
        username = session['username']
        email = creator["oerdc:email"]
        url = "http://connexions-oerpub.appspot.com/"
        post_values = {"username":username,"email":email,"slideshow_id":slideshare_id}
        data = urllib.urlencode(post_values)
        google_req = urllib2.Request(url, data)
        google_response = urllib2.urlopen(google_req)
        now_string = datetime.datetime.now().strftime('%Y%m%d-%H%M%S')
        temp_dir_name = '%s-%s' % (request.session['username'], now_string)
        save_dir = os.path.join(request.registry.settings['transform_dir'],temp_dir_name)
        os.mkdir(save_dir)
        request.session['upload_dir'] = temp_dir_name
        cnxml = clean_cnxml(cnxml)
        save_cnxml(save_dir,cnxml,[])
        return HTTPFound(location=request.route_url('metadata'))
        
        
        #return HTTPFound(location=request.route_url('updatecnx'))


    response = {'form':FormRenderer(form),"slideshare_id":slideshare_id,"google_resource_id":google_resource_id,"embed_google":embed_google,"embed_slideshare":embed_slideshare, "not_converted": not_converted, "show_iframe":show_iframe}
    return render_to_response(templatePath, response, request=request)
