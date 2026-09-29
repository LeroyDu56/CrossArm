MODULE ArrayProbe
    ! CrossArm - array probe: see tools/make_array_probe.py. PROC ArrProbe is what CrossArm converts;
    ! PROC Probe runs it in RobotStudio and writes the totals to HOME:/arrayprobe.txt.
    CONST num FEED{4}:=[1.5,-2,0.25,10];
    CONST num GRID{2,3}:=[[1,2,3],[40,50,60]];
    PERS num LIMIT{3}:=[5,-5,100];
    VAR num nSum:=0;
    VAR num nCalls:=0;
    VAR num nHits:=0;
    VAR num k:=0;

    PROC ArrProbe()
        nSum:=0;
        nCalls:=0;
        nHits:=0;
        FOR i FROM 1 TO 4 DO
            nSum:=nSum+FEED{i};
            IF FEED{i}<0 nHits:=nHits+1;
        ENDFOR
        FOR r FROM 1 TO 2 DO
            FOR c FROM 1 TO 3 DO
                nSum:=nSum+GRID{r,c};
                Weigh GRID{r,c},FEED{c};
            ENDFOR
        ENDFOR
        k:=1;
        WHILE LIMIT{k}>0 DO
            nHits:=nHits+10;
            k:=k+1;
        ENDWHILE
        nSum:=nSum+LIMIT{k};
    ENDPROC

    PROC Weigh(num a,num b)
        nCalls:=nCalls+a;
        IF b>1 nHits:=nHits+100;
    ENDPROC

    PROC Probe()
        VAR iodev file;
        ArrProbe;
        Open "HOME:" \File:="arrayprobe.txt", file \Write;
        Write file, "nSum " \Num:=nSum;
        Write file, "nCalls " \Num:=nCalls;
        Write file, "nHits " \Num:=nHits;
        Close file;
    ENDPROC
ENDMODULE
