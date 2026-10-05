MODULE StringProbe
    ! CrossArm - string probe: see tools/make_string_probe.py.
    VAR string strState;
    VAR string strWord;
    VAR string strNum;
    VAR string strLong;
    VAR string strApos;
    VAR string strEmpty;
    VAR num spA:=0;
    VAR num spO:=0;
    VAR num spSp:=0;
    VAR num spBang:=0;
    VAR num spOther:=0;
    VAR num spRuns:=0;
    VAR num spAt:=0;
    VAR num spMiss:=0;
    VAR num spNumLen:=0;
    VAR num spNumOk:=0;
    VAR num spLongLen:=0;
    VAR num spLongOk:=0;
    VAR num spSelf:=0;
    VAR num spEmpty:=0;
    VAR num spAposLen:=0;
    VAR num spApos:=0;
    VAR num spLocal:=0;
    VAR num spTakeLen:=0;
    VAR num spTake42:=0;
    VAR num spPart:=0;

    PROC StrCount()
        VAR num i:=1;
        VAR string ch;
        WHILE i<=StrLen(strWord) DO
            ch:=StrPart(strWord,i,1);
            IF ch="A" THEN
                Incr spA;
            ELSEIF ch="O" THEN
                Incr spO;
            ELSEIF ch=" " THEN
                Incr spSp;
            ELSEIF ch="!" THEN
                Incr spBang;
            ELSE
                Incr spOther;
            ENDIF
            Incr i;
        ENDWHILE
    ENDPROC

    PROC StrStep()
        IF strState="IDLE" THEN
            strState:="RUN";
        ELSEIF strState="RUN" THEN
            Incr spRuns;
            IF spRuns>=3 strState:="DONE";
        ENDIF
    ENDPROC

    PROC StrTake(string sIn)
        spTakeLen:=spTakeLen+StrLen(sIn);
        IF sIn="42" Incr spTake42;
    ENDPROC

    PROC StrLocal()
        VAR string sLoc:="X";
        sLoc:=sLoc+"Y";
        IF sLoc="XY" Incr spLocal;
    ENDPROC

    PROC StrProbe()
        spA:=0;
        spO:=0;
        spSp:=0;
        spBang:=0;
        spOther:=0;
        spRuns:=0;
        spAt:=0;
        spMiss:=0;
        spNumLen:=0;
        spNumOk:=0;
        spLongLen:=0;
        spLongOk:=0;
        spSelf:=0;
        spEmpty:=0;
        spAposLen:=0;
        spApos:=0;
        spLocal:=0;
        spTakeLen:=0;
        spTake42:=0;
        spPart:=0;
        strState:="IDLE";
        strWord:="LOAD. ROBOT!!";
        StrCount;
        WHILE strState<>"DONE" DO
            StrStep;
        ENDWHILE
        spAt:=StrMatch(strWord,1,"ROBOT");
        spMiss:=StrMatch(strWord,1,"XYZ");
        strNum:=NumToStr(spRuns,0)+"-"+ValToStr(spA);
        spNumLen:=StrLen(strNum);
        IF strNum="3-1" spNumOk:=1;
        strLong:="THE-QUICK-BROWN-FOX-JUMPS-OVER-THE-LAZY-DOG-0123456789-PACK-MY-BOX-WITH-FIVE-JUG";
        spLongLen:=StrLen(strLong);
        IF strLong="THE-QUICK-BROWN-FOX-JUMPS-OVER-THE-LAZY-DOG-0123456789-PACK-MY-BOX-WITH-FIVE-JUG" spLongOk:=1;
        strState:="<"+strState;
        IF strState="<DONE" spSelf:=1;
        strEmpty:="";
        spEmpty:=StrLen(strEmpty)+10;
        strApos:="it's";
        spAposLen:=StrLen(strApos);
        IF strApos="it's" spApos:=1;
        StrLocal;
        StrLocal;
        StrTake strNum;
        StrTake "42";
        StrTake strState;
        spPart:=StrLen(StrPart(strWord,7,5));
    ENDPROC

    PROC Probe()
        VAR iodev file;
        VAR num v;
        VAR bool ok;
        StrProbe;
        Open "HOME:" \File:="stringprobe.txt", file \Write;
        v:=spA;
        Write file, "spA " \Num:=v;
        v:=spO;
        Write file, "spO " \Num:=v;
        v:=spSp;
        Write file, "spSp " \Num:=v;
        v:=spBang;
        Write file, "spBang " \Num:=v;
        v:=spOther;
        Write file, "spOther " \Num:=v;
        v:=spRuns;
        Write file, "spRuns " \Num:=v;
        v:=spAt;
        Write file, "spAt " \Num:=v;
        v:=spMiss;
        Write file, "spMiss " \Num:=v;
        v:=spNumLen;
        Write file, "spNumLen " \Num:=v;
        v:=spNumOk;
        Write file, "spNumOk " \Num:=v;
        v:=spLongLen;
        Write file, "spLongLen " \Num:=v;
        v:=spLongOk;
        Write file, "spLongOk " \Num:=v;
        v:=spSelf;
        Write file, "spSelf " \Num:=v;
        v:=spEmpty;
        Write file, "spEmpty " \Num:=v;
        v:=spAposLen;
        Write file, "spAposLen " \Num:=v;
        v:=spApos;
        Write file, "spApos " \Num:=v;
        v:=spLocal;
        Write file, "spLocal " \Num:=v;
        v:=spTakeLen;
        Write file, "spTakeLen " \Num:=v;
        v:=spTake42;
        Write file, "spTake42 " \Num:=v;
        v:=spPart;
        Write file, "spPart " \Num:=v;
        Write file, "fact.case_equal " \Bool:="A"="a";
        Write file, "fact.space_equal " \Bool:="A"="A ";
        Write file, "fact.match_case " \Num:=StrMatch("load robot",1,"ROBOT");
        Write file, "fact.match_empty " \Num:=StrMatch("load robot",1,"");
        Write file, "fact.numtostr_half [" + NumToStr(2.5,0) + "]";
        v:=7;
        ok:=StrToVal("12AB",v);
        Write file, "fact.strtoval_12ab " \Num:=v;
        Write file, "fact.strtoval_12ab_ok " \Bool:=ok;
        Close file;
    ENDPROC
ENDMODULE
