MODULE RecordProbe
    ! CrossArm - record probe: see tools/make_record_probe.py.
    RECORD probeparams
        speeddata speed;
        zonedata zone;
    ENDRECORD
    RECORD probectrl
        num state;
        num counter;
        probeparams p;
        bool busy;
        string label;
    ENDRECORD
    RECORD probetally
        num n;
        bool seen;
    ENDRECORD
    VAR probectrl recCtrl;
    PERS probectrl recSaved:=[0,7,[[300,500,5000,1000],[FALSE,20,30,30,3,30,4.5]],FALSE,"SAVED"];
    VAR probetally tallyLast;
    VAR probetally tallyCopy;
    CONST robtarget pA:=[[1100,50,1000],[0,1,0,0],[0,0,0,0],[9E+09,9E+09,9E+09,9E+09,9E+09,9E+09]];
    CONST robtarget pB:=[[1100,250,1000],[0,1,0,0],[0,0,0,0],[9E+09,9E+09,9E+09,9E+09,9E+09,9E+09]];
    CONST robtarget pC:=[[1100,250,800],[0,1,0,0],[0,0,0,0],[9E+09,9E+09,9E+09,9E+09,9E+09,9E+09]];
    CONST jointtarget jStart:=[[0,0,0,0,-90,0],[9E+09,9E+09,9E+09,9E+09,9E+09,9E+09]];
    VAR num nSteps:=0;
    VAR num nBusy:=0;
    VAR num nSaved:=0;
    VAR num nBad:=0;
    VAR num nCopy:=0;
    VAR num nTime:=0;
    VAR num nTime2:=0;
    VAR clock ckProbe;

    PROC RecInit()
        recCtrl.counter:=0;
        recCtrl.p.speed:=[400,500,5000,1000];
        recCtrl.p.zone:=z50;
        recCtrl.busy:=FALSE;
    ENDPROC

    PROC RecStepA()
        recCtrl.state:=1;
        recCtrl.counter:=recCtrl.counter+1;
        recCtrl.busy:=TRUE;
    ENDPROC

    PROC RecStepB()
        IF recCtrl.state=1 THEN
            recCtrl.state:=2;
            recCtrl.counter:=recCtrl.counter+10;
        ENDIF
        recCtrl.busy:=FALSE;
    ENDPROC

    PROC RecCount()
        VAR probetally tallyNow;
        IF tallyNow.n<>0 nBad:=nBad+1;
        IF recCtrl.busy nBusy:=nBusy+1;
        IF recCtrl.busy tallyLast.seen:=TRUE;
        tallyNow.n:=nSteps+1;
        nSteps:=tallyNow.n;
        tallyLast.n:=nSteps;
    ENDPROC

    PROC RecProbe()
        nSteps:=0;
        nBusy:=0;
        nSaved:=0;
        nBad:=0;
        nCopy:=0;
        tallyLast.n:=0;
        tallyLast.seen:=FALSE;
        recCtrl.state:=0;
        RecInit;
        WHILE recCtrl.state<>3 DO
            TEST recCtrl.state
            CASE 0:
                RecStepA;
            CASE 1:
                RecStepB;
            DEFAULT:
                recCtrl.state:=3;
            ENDTEST
            RecCount;
        ENDWHILE
        nSaved:=recSaved.counter+recSaved.p.speed.v_tcp;
        IF NOT recSaved.busy nSaved:=nSaved+1000;
        tallyCopy:=tallyLast;
        IF tallyCopy.seen THEN
            nCopy:=tallyCopy.n+100;
        ELSE
            nCopy:=tallyCopy.n;
        ENDIF
        MoveAbsJ jStart,v1000,fine,tool0;
        MoveJ pA,v1000,fine,tool0;
        ClkReset ckProbe;
        ClkStart ckProbe;
        MoveL pB,recCtrl.p.speed,fine,tool0;
        ClkStop ckProbe;
        nTime:=ClkRead(ckProbe);
        ClkReset ckProbe;
        ClkStart ckProbe;
        MoveL pC,recCtrl.p.speed,recCtrl.p.zone,tool0;
        MoveL pA,recCtrl.p.speed,fine,tool0;
        ClkStop ckProbe;
        nTime2:=ClkRead(ckProbe);
    ENDPROC

    PROC Probe()
        VAR iodev file;
        ConfJ\Off;
        ConfL\Off;
        recCtrl.label:="IDLE";
        RecProbe;
        Open "HOME:" \File:="recordprobe.txt", file \Write;
        Write file, "state " \Num:=recCtrl.state;
        Write file, "counter " \Num:=recCtrl.counter;
        Write file, "nSteps " \Num:=nSteps;
        Write file, "nBusy " \Num:=nBusy;
        Write file, "nSaved " \Num:=nSaved;
        Write file, "nBad " \Num:=nBad;
        Write file, "nCopy " \Num:=nCopy;
        Write file, "nTime " \Num:=nTime;
        Write file, "nTime2 " \Num:=nTime2;
        Write file, "label " + recCtrl.label;
        Close file;
    ENDPROC
ENDMODULE
