# -*- coding: utf-8 -*-

import codecs
import xbmc
import xbmcvfs
import xbmcaddon
import unicodedata
import urllib
from traceback import format_exc
from xbmcgui import Dialog
from json import loads
from urllib.parse import unquote, unquote_plus, urlparse

__addon__ = xbmcaddon.Addon()


def download(self, ID, dest):
    try:
        import zlib, base64

        down_id = [
            ID,
        ]
        result = self.server.DownloadSubtitles(self.osdb_token, down_id)
        if result["data"]:
            local_file = open(dest, "w" + "b")
            d = zlib.decompressobj(16 + zlib.MAX_WBITS)
            data = d.decompress(base64.b64decode(result["data"][0]["data"]))
            local_file.write(data)
            local_file.close()
            log(__name__, "Download Using XMLRPC")
            return True
        return False
    except:
        return False


def getlastsplit(firsrarfile, x):
    if firsrarfile[-3:] == "001":
        return firsrarfile[:-3] + ("%03d" % (x + 1))
    if firsrarfile[-11:-6] == ".part":
        return firsrarfile[0:-6] + ("%02d" % (x + 1)) + firsrarfile[-4:]
    if firsrarfile[-10:-5] == ".part":
        return firsrarfile[0:-5] + ("%1d" % (x + 1)) + firsrarfile[-4:]
    return firsrarfile[0:-2] + ("%02d" % (x - 1))


def getDomain():
    try:
        url = "https://pastebin.com/raw/1vbRPSGh"
        req = urllib.request.urlopen(url)
        domain = str(req.read())
        return domain
    except Exception as err:
        log(
            f"Caught Exception: error in finding getDomain: {format(err)}",
            xbmc.LOGERROR,
        )
        log(format_exc(), xbmc.LOGERROR)
        return "lolfw.com"


def convert_to_utf(file):
    try:
        with codecs.open(file, "r", "cp1255") as f:
            srt_data = f.read()

        with codecs.open(file, "w", "utf-8") as output:
            output.write(srt_data)
    except Exception as err:
        log(f"Caught Exception: error converting to utf: {format(err)}", xbmc.LOGERROR)
        log(format_exc(), xbmc.LOGERROR)
        pass


def normalizeString(str):
    return unicodedata.normalize("NFKD", str)


def cleanFolders(folder):
    try:
        xbmcvfs.rmtree(folder)
    except Exception as err:
        log(f"Caught Exception: error deleting folders: {format(err)}", xbmc.LOGERROR)
        log(format_exc(), xbmc.LOGERROR)
        pass
    xbmcvfs.mkdirs(folder)


def uploadAP(params):
    # Upload AP
    try:
        if urlparse(xbmc.Player().getPlayingFile()).hostname[-11:] == "tv4.live":
            Ap = 1
    except:
        pass

    if params and Ap == 1 and __addon__.getSetting("uploadAP") == "true":
        try:
            url = f'http://subs.vpnmate.com/webupload.php?status=1&imdb={getParam("imdb", params)}&season={getParam("season", params)}&episode={getParam("episode", params)}'
            req = urllib.request.urlopen(url)
            ap_object = loads(req.read())["result"]
            if ap_object["lang"]["he"] == 0:
                xbmc.sleep(30 * 1000)
                i = Dialog().yesno(
                    "Apollo Upload Subtitle",
                    f"Media version {ap_object['version']}",
                    "This subtitle is 100% sync and match?",
                )
                if i == 1:
                    url = f'http://subs.vpnmate.com/webupload.php?upload=1&lang=he&subid={getParam("id", params)}&imdb={getParam("imdb", params)}&season={getParam("season", params)}&episode={getParam("episode", params)}'
                    req = urllib.request.urlopen(url)
                    ap_upload = loads(url.read())["result"]
                    if "error" in ap_upload:
                        Dialog().ok("Apollo Error", f'{ ap_upload["error"] }')
                    else:
                        Dialog().ok("Apollo", "Sub uploaded. Thank you!")
        except:
            pass


def getParam(name, params):
    try:
        return unquote_plus(params[name])
    except Exception as err:
        log(f"Caught Exception: error getting param: {format(err)}", xbmc.LOGERROR)
        log(format_exc(), xbmc.LOGERROR)
        pass


def log(msg, level=xbmc.LOGDEBUG):
    xbmc.log(f"##**## [Wizdom Subs] {msg}", level=level)
