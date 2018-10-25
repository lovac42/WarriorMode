# -*- coding: utf-8 -*-
# Copyright: (C) 2018 Lovac42
# Support: https://github.com/lovac42/WarriorMode
# License: GNU GPL, version 3 or later; http://www.gnu.org/copyleft/gpl.html
# Version: 0.0.3

# Other Authors:
# Copyright (c) 2018 ijgnd (https://ankiweb.net/shared/info/673114053)
# Copyright (c) 2016-2017 Glutanimate (https://ankiweb.net/shared/info/1008566916)
# Copyright (c) 2013 Steve AW (https://github.com/steveaw/anki_addons/blob/master/reviewer_show_cardinfo.py)
# Copyright (c) 2012 Damien Elmes (https://ankiweb.net/shared/info/2179254157)


########################################
###   THIS  IS  AN  ALPHA  RELEASE   ###
###     Please check for updates     ###
########################################



#Todo include sibling info



from __future__ import division

############## USER CONFIGURATION START ##############


HOTKEY = 'Shift+W'

REVLOG_HIDE_FILTERED = False
REVLOG_HIDE_RESCHEDULED = False
SHOW_DETAILLED_CARD_STATS_FOR_CURRENT_CARD = True

MULTILINE_LONG_OPTION_GROUP_NAMES = True
HIDE_TIME_COLUMN_FROM_REVLOG = True

LOW_CRITICAL_COLOR = "Red"
HIGH_CRITICAL_COLOR = "Blue"


IVL_MOD_COLOR_THRESHOLDS = (70,110) #n<=70=RED, n>=110=BLUE
LAPSE_MOD_COLOR_THRESHOLDS= (30,70) #n<=30=RED, n>=70=BLUE


CSS_STYLING = """
body {
    color: %s;
    background-color: %s;
    margin: 8px;
}
p { 
    margin-top: 1em;
    margin-bottom: 1em;
}
h1,h2,h3,h4{
    display: block;
    font-size: 1.17em;
    margin-top: 1em;
    margin-bottom: 1em;
    margin-left: 0;
    margin-right: 0;
    font-weight: bold;
}
"""
##############  USER CONFIGURATION END  ##############



from anki.hooks import addHook
from aqt import mw
from aqt.qt import *
from aqt.webview import AnkiWebView
import aqt.stats
import time
import datetime
from anki.lang import _
from anki.utils import fmtTimeSpan
from anki.stats import CardStats, CollectionStats
from aqt.utils import showWarning, showText


from anki import version
ANKI21 = version.startswith("2.1.")
if not ANKI21:
    import anki.js
    QWebEngineView=QWebView


freezeMode=False #Pause current card updates
night_mode_state=False


class DockableWithClose(QDockWidget):
    closed = pyqtSignal()
    def closeEvent(self, evt):
        self.closed.emit()
        QDockWidget.closeEvent(self, evt)
    def __init__(self,t,m):
        QDockWidget.__init__(self,t,m)
        self.setStyleSheet("""
 *{
     selection-background-color: yellow;
 }
 QDockWidget {
     border: 0px solid darkgray;
     text-align: left;
     background: darkgray;
     padding-left: 5px;
 }
 QDockWidget::title {
     text-align: left;
     background: darkgray;
     padding-left: 5px;
 }
 QDockWidget::close-button, QDockWidget::float-button {
     border: 1px solid transparent;
     background: darkgray;
     padding: 0px;
 }
 QDockWidget::close-button:hover, QDockWidget::float-button:hover {
     background: gray;
 }
 QDockWidget::close-button:pressed, QDockWidget::float-button:pressed {
     padding: 1px -1px -1px 1px;
 }
""")



class StatsSidebar():
    killed=False
    dock = None
    web = None

    def __init__(self, type, title):
        self.type = type
        self.title = title
        addHook('unloadProfile', self.hide)
        addHook("showQuestion", self._update)
        addHook('afterStateChange', self.onAfterStateChange)

    def onAfterStateChange(self, newS, oldS, *args):
        if newS != 'review': self._update()

    def _addDockable(self):
        self.web = QWebEngineView()
        self.dock = DockableWithClose(_(self.title), mw)
        self.dock.setObjectName(_(self.title))
        self.dock.setWidget(self.web)
        self.dock.closed.connect(self._onClosed)
        self.dock.setAllowedAreas(Qt.BottomDockWidgetArea | Qt.RightDockWidgetArea | Qt.LeftDockWidgetArea)
        if self.type>10:
            pos=Qt.RightDockWidgetArea
        elif self.type<-10:
            pos=Qt.LeftDockWidgetArea
        else:
            pos=Qt.BottomDockWidgetArea
        mw.addDockWidget(pos, self.dock)

    def _onClosed(self):
        # schedule removal for after evt has finished
        QTimer.singleShot(100, self.hide)
        self.killed=True

    def show(self):
        if not self.dock:
            self._addDockable()
        elif not self.killed:
            self.dock.show()
        QTimer.singleShot(10, self._update)

    def hide(self):
        if self.dock:
            self.dock.hide()





    #copy and paste from Browser
    #Added IntDate column
    def _revlogData(self, card, cs):
        entries = mw.col.db.all(
            "select id/1000.0, ease, ivl, lastIvl, factor, time/1000.0, type "
            "from revlog where cid = ?", card.id)
        if not entries:
            return "No Review Logs"

        s = "<table width=100%%><tr><th align=left>%s</th>" % _("Date")
        s += ("<th align=right>%s</th>" * 6) % (
            _("Type"), _("G"), _("Ivl"),  _("LIvl"), "IntDate", _("Ease"))
        if not HIDE_TIME_COLUMN_FROM_REVLOG:
            s += ("<th align=right>%s</th>") % (_("Time"))

        cnt = 0
        for (date, ease, ivl, lastIvl, factor, taken, type) in reversed(entries):
            cnt += 1
            if REVLOG_HIDE_FILTERED and type==3: continue
            if REVLOG_HIDE_RESCHEDULED and type>3: continue

            s += "<tr><td>%s</td>" % time.strftime(_("<b>%Y-%m-%d</b> @ %H:%M"),
                                                   time.localtime(date))
            tstr = [_("Lrn"), _("Rev"), _("ReLn"), _("Filt"), _("Resched")][type]
                #Learned, Review, Relearned, Filtered, Defered (Rescheduled)


            #COLORIZE LOG TYPE
            import anki.stats as st
            fmt = "<span style='color:%s'>%s</span>"
            if type == 0: #Learn
                tstr = fmt % (st.colLearn, tstr)
            elif type == 1: #Review
                tstr = fmt % (st.colMature, tstr)
            elif type == 2: #Relearn
                tstr = fmt % (st.colRelearn, tstr)
            elif type == 3: #Cram
                tstr = fmt % ("orange", tstr)
            else: #Others (Reschedule)
                tstr = fmt % ("#000", tstr)

            #COLORIZE EASE
            if ease == 1:
                ease = fmt % (st.colRelearn, ease)
            elif ease == 3:
                ease = fmt % ('navy', ease)
            elif ease == 4:
                ease = fmt % ('darkgreen', ease)



                ####################
            int_due = "na"
            if ivl > 0:
                int_due_date = time.localtime(date + (ivl * 24 * 60 * 60))
                int_due = time.strftime(_("%Y-%m-%d"), int_due_date)
                ####################

            ivl = self.formatIvlString(cs, ivl)
            lastIvl = self.formatIvlString(cs, lastIvl)

            s += ("<td align=right>%s</td>" * 6) % (
                tstr, ease, ivl, lastIvl, int_due,
                "%.2f" % (factor / 1000.0) if factor else "")

            if not HIDE_TIME_COLUMN_FROM_REVLOG:
                s += "<td align=right>%s</td>" % cs.time(taken)
            s += "</tr>"

        s += "</table>"

        if REVLOG_HIDE_FILTERED:
            s += _("""Note: Filtered deck history is hidden.""")
        if REVLOG_HIDE_RESCHEDULED:
            s += _("""Note: Rescheduled deck history is hidden.""")
        if cnt < card.reps:
            s += _("""\
Note: Some of the history is missing. For more information, \
please see the browser documentation.""")
        return s


    def formatIvlString(self, cs, ivl):
        if ivl == 0:
            return _("0d")
        elif ivl > 0:
            return fmtTimeSpan(ivl * 86400, short=True)
        else:
            return cs.time(-ivl)



    def critical_color(self,valueInt, colorconfig):
            if valueInt <= colorconfig[0]:
                return LOW_CRITICAL_COLOR
            elif valueInt >=  colorconfig[1]:
                return HIGH_CRITICAL_COLOR
            else:
                return ""


    def mini_card_stats(self,card):
        overdue=mw.col.sched._daysLate(card)
        ease=card.factor/1000.0
        # try:
        lrRatio=card.lapses/card.reps*100.0 if card.reps else 0
        # except ZeroDivisionError:
            # lrRatio=0

        txt = """<p><table width="100%" align="left"><tr>
<td><b>Due</b></td>
<td><b>Ivl</b></td>
<td><b>Ease</b></td>
<td><b>EF*Ivl</b></td>
<td><b>Lapse</b></td>
<td><b>Reps</b></td>
<td><b>L/R</b></td>
<td><b>Left</b></td>
</tr><tr>"""
        txt += "<td>%dd</td>"% -overdue
        txt += "<td>%dd</td>"% card.ivl
        txt += "<td>%.2f</td>"% ease
        txt += "<td>%dd</td>"% int((card.ivl + overdue//2) *ease) #does not acct for modifier
        txt += "<td>%d</td>"% card.lapses
        txt += "<td>%d</td>"% card.reps
        txt += "<td>%.2f%%</td>"% lrRatio
        txt += "<td>%d</td>"% (card.left%1000)
        txt += "</tr></table></p><hr>"
        return txt





    def _update(self):
        if not self.dock or not self.dock.isVisible(): return
        if freezeMode and self.type>10: return

        card = mw.reviewer.card
        txt = _("No Current Card")

        if self.type<-10:
            txt = _("No Last Card")
            card = mw.reviewer.lastCard()

        cs = CollectionStats(mw.col)
        cs.wholeCollection=True if self.type<0 else False

        if self.type==0: #review count
            txt = "<center>%s</center>" % mw.reviewer._remaining() if mw.state=="review" else '? + ? + ?'
        elif abs(self.type)==1: #todayStats
            txt = "<center>%s</center>" % cs.todayStats()
        elif abs(self.type)==2: #forecast chart
            if not card or card.odid: #no filtered decks
                return
            if ANKI21:
                p=mw.mediaServer.getPort()
                txt = """
<script src="http://localhost:%d/_anki/jquery.js"></script>
<script src="http://localhost:%d/_anki/plot.js"></script>
<center>%s</center>
""" % (p,p,self.dueGraph(cs))

            else:
                txt = "<script>%s\n</script><center>%s</center>" % (
                    anki.js.jquery+anki.js.plot, self.dueGraph(cs))

        elif abs(self.type)>=90:
            txt = self.customViews(card)

        elif mw.state!='review' and self.type>10:
            txt = _("No Review Card")

        elif card: #left or right col
            cs = CardStats(mw.col, card)
            if abs(self.type)==12: #card rev log
                txt = self._revlogData(card, cs)
            else: #card stats
                txt = self.deckOptionsInfo(card)
                txt += _("<h3>Card Stats:</h3>")
                txt += self.mini_card_stats(card)
                txt +=  cs.report()

                did = card.odid if card.odid else card.did
                fdid = card.did if card.odid else 0
                deckName = mw.col.decks.get(did)['name'] #in case of filtered decks
                tags=mw.col.getNote(card.nid).stringTags()
                txt += """<table width="100%%"><tr>
<td><b>Deck ID:</b></td> <td>%d</td></tr><tr>
<td><b>Fil DID:</b></td> <td>%d</td></tr><tr>
<td><b>oDeck:</b></td> <td>%s</td></tr><tr>
<td><b>Tags:</b></td> <td>%s</td>
</tr></table>""" % (did, fdid, deckName, tags)

        style = self._style()
        self.web.setHtml("""
<!doctype html><html><head><style>%s</style></head>
<body>%s</body></html>""" % (style, txt))



#copied and modded from anki.stats.dueGraph
    def dueGraph(self, cs):
        start = 0; end = 31;
        d = cs._due(start, end)
        yng = []
        mtr = []
        tot = 0
        totd = []
        for day in d:
            yng.append((day[0], day[1]))
            mtr.append((day[0], day[2]))
            tot += day[1]+day[2]
            totd.append((day[0], tot))
        data = [
            dict(data=mtr, color="#070", label=_("")),
            dict(data=yng, color="#7c7", label=_("")),
        ]
        if len(totd) > 1:
            data.append(
                dict(data=totd, color="rgba(0,0,0,0.9)", label=_(""), yaxis=2,
                     bars={'show': False}, lines=dict(show=True), stack=False))
        xaxis = dict(tickDecimals=0, min=-0.5)
        if end is not None:
            xaxis['max'] = end-0.5
        txt = cs._graph(id="due", data=data, ylabel2=_(""), conf=dict(
                xaxis=xaxis, yaxes=[dict(min=0), dict(
                    min=0, tickDecimals=0, position="right")]))
        return txt



    def deckOptionsInfo(self, card):
        if card.odid:   #filtered decks
            txt = _("<h3>Filtered Deck Options</h3>")
            conf=mw.col.decks.confForDid(card.odid)
            filConf = mw.col.decks.confForDid(card.did)
            newsteps = filConf['delays'] or conf['lapse']['delays']

        else:   #regular decks
            txt = _("<h3>Deck Options</h3>")
            conf=mw.col.decks.confForDid(card.did)
            if card.type==2: #rev
                newsteps=conf['lapse']['delays']
            else: #new
                newsteps=conf['new']['delays']

        formatted_steps = ''
        for i in newsteps:
            formatted_steps += ' -- ' + fmtTimeSpan(i * 60, short=True)
        GraduatingIvl=conf['new']['ints'][0]
        EasyIvl=conf['new']['ints'][1]

        im=conf['rev']['ivlFct']
        easybonus=conf['rev']['ease4']
        lnivl=conf['lapse']['mult']
        optiongroup=conf['name']

        ogv = 0
        ogr = 15
        optiongroup_fmt = ""
        while ogv < len(optiongroup):
            optiongroup_fmt += optiongroup[ogv:ogv+ogr] + '\n'
            ogv = ogv+ogr
        optiongroup_fmt = optiongroup_fmt.rstrip('\n')

        txt += """<p><table width=100%><tr> 
            <td align=left style='padding-right: 3px;'><b>OptGr</b></td>
            <td align=left style='padding-right: 3px;'><b>Step</b></td>
            <td align=left style='padding-right: 3px;'><b>GrIv</b></td>
            <td align=left style='padding-right: 3px;'><b>EaIv</b></td>
            <td align=left style='padding-right: 3px;'><b>EaBo</b></td>
            <td align=left style='padding-right: 3px;'><b>IvMo</b></td>
            <td align=left style='padding-right: 3px;'><b>LpIv</b></td>
        </tr>"""

        txt += "<tr>" 
        # option group names can be very long
        if len(optiongroup) > 15 and MULTILINE_LONG_OPTION_GROUP_NAMES:
            txt += "<td align=left style='padding-right: 3px;'> %s </td>" % optiongroup_fmt
        else:
            txt += "<td align=left style='padding-right: 3px;'> %s </td>" % optiongroup
        txt += "<td align=left style='padding-right: 3px;'> %s </td>" % str(newsteps)[1:-1]
        txt += "<td align=left style='padding-right: 3px;'> %s </td>" % str(GraduatingIvl)
        txt += "<td align=left style='padding-right: 3px;'> %s </td>" % str(EasyIvl)
        txt += "<td align=left style='padding-right: 3px;'> %s </td>" % str(int(100 * easybonus))
        txt += '<td align=left style="padding-right: 3px;"> <div style="color: %s;"> %s </div></td>' % ( self.critical_color(int(100 * im),   IVL_MOD_COLOR_THRESHOLDS  ), str(int(100 * im)    ))
        txt += '<td align=left style="padding-right: 3px;"> <div style="color: %s;"> %s </div></td>' % ( self.critical_color(int(100 * lnivl),LAPSE_MOD_COLOR_THRESHOLDS), str(int(100 * lnivl) ))
        txt += "</tr>"
        txt += "</table></p><hr>"
        return txt





    def _style(self):
        #CHECK NIGHT MODE
        if night_mode_state:
            txtColor='aqua'
            bgColor='#272828'
        else:
            txtColor="#333"
            bgColor="#dedede"

        css=CSS_STYLING %(txtColor, bgColor)
        if ANKI21:
            return css + " td { font-size: 80%; }"
        return css


# RETURN CUSTOM STATS BELOW
##################################
    def customViews(self, card):
        if not card: return
        txt = card.q()
        return txt






class WarriorMode:
    key="WarriorMode"
    geometry = None
    state = None
    dualMon=False
    # shown = False
    docks = []


    def __init__(self):
        menu=None
        for a in mw.form.menubar.actions():
            if '&Debug' == a.text():
                menu=a.menu()
                menu.addSeparator()
                break
        if not menu:
            menu=mw.form.menubar.addMenu('&Debug')

        mw.setCorner(Qt.BottomRightCorner, Qt.RightDockWidgetArea)
        mw.setCorner(Qt.BottomLeftCorner, Qt.LeftDockWidgetArea)
        if mw.width() < 600: mw.resize(QSize(600, mw.height()))

        act=QAction("WM: Reset Workspace", mw)
        act.triggered.connect(self.reset)
        menu.addAction(act)

        act=QAction("WM: Dual Monitors", mw)
        act.setCheckable(True)
        act.triggered.connect(self.dualMonSetup)
        menu.addAction(act)

        act=QAction("WM: Freeze CCard View", mw)
        act.setCheckable(True)
        act.triggered.connect(self.freezeUpdates)
        menu.addAction(act)

        act=QAction("Warrior Mode", mw)
        act.setCheckable(True)
        act.setShortcut(QKeySequence(HOTKEY))
        act.triggered.connect(self.toggle)
        menu.addAction(act)
        self.action=act

        addHook('profileLoaded', self.onProfileLoaded)
        addHook('unloadProfile', self.onUnloadProfile)
        addHook("night_mode_state_changed", self.refresh)


    def onProfileLoaded(self):
        if mw.pm.profile.get(self.key+"State"):
            self.state=mw.pm.profile[self.key+"State"]
            mw.restoreState(self.state)
        if mw.pm.profile.get(self.key+"Geom"):
            self.geometry=mw.pm.profile[self.key+"Geom"]
            mw.restoreGeometry(self.geometry)


    def onUnloadProfile(self):
        if self.state:
            self.on(); #fix saving positions
            mw.pm.profile[self.key+"State"]=self.state
            mw.pm.profile[self.key+"Geom"]=self.geometry


    def refresh(self, state):
        global night_mode_state
        night_mode_state=state
        for d in self.docks:
            d._update()

    def freezeUpdates(self): #to compare b4/after changes
        global freezeMode
        if freezeMode:
            freezeMode=False
            for d in self.docks: d._update()
        else: freezeMode=True

    def reset(self):
        self.state=self.geometry=None
        self.action.setChecked(True)
        for d in self.docks:
            d.killed=False
            d.hide()
            d.show()

    def toggle(self):
        if not self.docks: self.setup()

        shown=False; allKilled=True
        for d in self.docks:
            if d.dock and d.dock.isVisible(): shown=True; break;
            if not d.killed: allKilled=False;

        if shown: #OFF
            self.off()
        elif allKilled:
            self.reset()
        else:
            self.on()

    def off(self):
        self.state=mw.saveState()
        self.geometry=mw.saveGeometry()
        for d in self.docks: d.hide()

    def on(self):
        for d in self.docks: d.show()
        if self.state: mw.restoreState(self.state)
        if self.geometry: mw.restoreGeometry(self.geometry)

    def dualMonSetup(self):
        if self.dualMon: return
        self.dualMon=True
        if not self.docks: self.setup()

        d = StatsSidebar(0, "Remaining Reviews (Deck)")
        self.docks.append(d)
        d = StatsSidebar(1, "Todays Stats (Deck)")
        self.docks.append(d)
        d = StatsSidebar(-2, "Forecast Chart (Collection)")
        self.docks.append(d)
        self.on()

    def setup(self):
        #1-9, Negative = whole collection, pos = per deck
        d = StatsSidebar(2, "Forecast Chart (Deck)")
        self.docks.append(d)
        d = StatsSidebar(-1, "Todays Stats (Collection)")
        self.docks.append(d)

        #11-19, Neg = lastCard, leftDock; pos = currentCard, rightDock
        d = StatsSidebar(11, "Current Card Info")
        self.docks.append(d)
        d = StatsSidebar(12, "Current Card History")
        self.docks.append(d)

        d = StatsSidebar(-11, "Previous Card Info")
        self.docks.append(d)
        d = StatsSidebar(-12, "Previous Card History")
        self.docks.append(d)

        # #ADD CUSTOM DOCKS BELOW (modify customView)
        # #use 90-99
        # ##################################
        # d = StatsSidebar(-91, "Card Q")
        # self.docks.append(d)

        # # if not self.dualMon: return
        # # More Custom Cr... Stuff Below

        # d = StatsSidebar(91, "Card A")
        # self.docks.append(d)

ws=WarriorMode()
