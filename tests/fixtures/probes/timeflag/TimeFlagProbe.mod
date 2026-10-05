MODULE TimeFlagProbe
    ! CrossArm - time flag probe: see tools/make_time_flag_probe.py.
    VAR bool tfNever;
    VAR bool tfReady;
    VAR bool tfLate;
    VAR clock tfClock;
    VAR num tfLate1:=0;
    VAR num tfLate2:=0;
    VAR num tfTime1:=0;
    VAR num tfTime2:=0;

    PROC TfProbe()
        tfLate1:=0;
        tfLate2:=0;
        tfTime1:=0;
        tfTime2:=0;
        tfNever:=FALSE;
        tfReady:=TRUE;
        ClkReset tfClock;
        ClkStart tfClock;
        WaitUntil tfNever\MaxTime:=1.5\TimeFlag:=tfLate;
        ClkStop tfClock;
        tfTime1:=ClkRead(tfClock);
        IF tfLate tfLate1:=1;
        ClkReset tfClock;
        ClkStart tfClock;
        WaitUntil tfReady\MaxTime:=1.5\TimeFlag:=tfLate;
        ClkStop tfClock;
        tfTime2:=ClkRead(tfClock);
        IF tfLate tfLate2:=1;
    ENDPROC

    PROC Probe()
        VAR iodev file;
        VAR num v;
        TfProbe;
        Open "HOME:" \File:="timeflagprobe.txt", file \Write;
        v:=tfLate1;
        Write file, "tfLate1 " \Num:=v;
        v:=tfLate2;
        Write file, "tfLate2 " \Num:=v;
        v:=tfTime1;
        Write file, "tfTime1 " \Num:=v;
        v:=tfTime2;
        Write file, "tfTime2 " \Num:=v;
        Close file;
    ENDPROC
ENDMODULE
