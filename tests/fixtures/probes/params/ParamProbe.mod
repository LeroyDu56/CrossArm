MODULE ParamProbe
    ! CrossArm - parameter probe: see tools/make_param_probe.py. PROC ParProbe is what CrossArm converts;
    ! PROC Probe runs it in RobotStudio and writes the totals to HOME:/paramprobe.txt.
    RECORD partspec
        string name;
        num passes;
        num depth;
        bool chamfer;
    ENDRECORD
    PERS partspec psA:=["PART-A",3,0.5,TRUE];
    PERS partspec psB:=["PART-B",2,-1.25,FALSE];
    VAR num nSum:=0;
    VAR num nCount:=0;
    VAR num nBack:=0;

    PROC ParProbe()
        nSum:=0;
        nCount:=0;
        nBack:=0;
        Work psA;
        Work psB;
        Bump nBack,4;
        Bump nBack,-1.5;
        Twice nBack;
        Decr nCount;
        Add nSum,10;
        Clear nCount;
        Incr nCount;
        Work psA;
    ENDPROC

    PROC Work(partspec part)
        FOR i FROM 1 TO part.passes DO
            nSum:=nSum+part.depth;
        ENDFOR
        IF part.chamfer THEN
            nCount:=nCount+10;
        ELSE
            nCount:=nCount+1;
        ENDIF
    ENDPROC

    PROC Bump(INOUT num n,num d)
        Add n,d;
    ENDPROC

    PROC Twice(INOUT num n)
        Bump n,1;
        Incr n;
    ENDPROC

    PROC Probe()
        VAR iodev file;
        ParProbe;
        Open "HOME:" \File:="paramprobe.txt", file \Write;
        Write file, "nSum " \Num:=nSum;
        Write file, "nCount " \Num:=nCount;
        Write file, "nBack " \Num:=nBack;
        Close file;
    ENDPROC
ENDMODULE
