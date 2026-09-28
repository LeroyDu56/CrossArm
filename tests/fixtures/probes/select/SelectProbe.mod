MODULE SelectProbe
    ! CrossArm - select probe: see tools/make_select_probe.py. PROC SelProbe is what CrossArm converts;
    ! PROC Probe runs it in RobotStudio and writes the totals to HOME:/selectprobe.txt.
    VAR num nMode:=0;
    VAR num nSum:=0;
    VAR num nCalls:=0;
    VAR num nPath:=0;
    CONST num KIND:=2;

    PROC SelProbe()
        nSum:=0;
        nCalls:=0;
        nPath:=0;
        FOR i FROM -1 TO 4 DO
            nMode:=i;
            TEST nMode
            CASE 1, 2:
                nSum:=nSum+10;
                nPath:=nPath+1;
                TEST nMode
                CASE 2:
                    nPath:=nPath+10;
                ENDTEST
            CASE -1:
                nSum:=nSum+100;
            CASE 3:
                SelCount;
            CASE 4:
            DEFAULT:
                nSum:=nSum+1000;
                nPath:=nPath+1;
            ENDTEST
        ENDFOR
        nMode:=7;
        TEST nMode
        CASE 1:
            nSum:=nSum+5;
        CASE 7:
            SelCount;
        ENDTEST
        nMode:=8;
        TEST nMode
        CASE 1:
            nSum:=nSum+5;
            nPath:=nPath+5;
        ENDTEST
        nMode:=2.5;
        TEST nMode
        CASE 2.5:
            nSum:=nSum+20000;
            nPath:=nPath+1;
        DEFAULT:
            nSum:=nSum+50000;
        ENDTEST
        TEST KIND
        CASE 2:
            nPath:=nPath+100;
        DEFAULT:
            nPath:=nPath+1000;
        ENDTEST
        SelArg 3;
        SelArg 8;
    ENDPROC

    PROC SelCount()
        nCalls:=nCalls+1;
    ENDPROC

    PROC SelArg(num k)
        TEST k
        CASE 3:
            nCalls:=nCalls+10;
        DEFAULT:
            nCalls:=nCalls+100;
        ENDTEST
    ENDPROC

    PROC Probe()
        VAR iodev file;
        SelProbe;
        Open "HOME:" \File:="selectprobe.txt", file \Write;
        Write file, "nSum " \Num:=nSum;
        Write file, "nCalls " \Num:=nCalls;
        Write file, "nPath " \Num:=nPath;
        Close file;
    ENDPROC
ENDMODULE
