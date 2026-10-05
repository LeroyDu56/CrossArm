MODULE PointRefProbe
    ! CrossArm - probe of points passed by reference: see tools/make_point_ref_probe.py.
    CONST robtarget prStart:=[[1100,50,1000],[0,1,0,0],[0,0,0,0],[9E+09,9E+09,9E+09,9E+09,9E+09,9E+09]];
    CONST jointtarget prHome:=[[0,0,0,0,-90,0],[9E+09,9E+09,9E+09,9E+09,9E+09,9E+09]];
    VAR robtarget prCur;
    VAR num prY1:=0;
    VAR num prY2:=0;
    VAR num prZ:=0;
    VAR num prX:=0;
    VAR num prSteps:=0;

    PROC PrShift(VAR robtarget pAt)
        pAt:=Offs(pAt,0,50,0);
        MoveL pAt,v400,fine,tool0;
        Incr prSteps;
    ENDPROC

    PROC PrLift(INOUT robtarget pAt,num nDown)
        pAt.trans.z:=pAt.trans.z-nDown;
        PrShift pAt;
    ENDPROC

    PROC PrProbe()
        prY1:=0;
        prY2:=0;
        prZ:=0;
        prX:=0;
        prSteps:=0;
        MoveAbsJ prHome,v1000,fine,tool0;
        prCur:=prStart;
        MoveJ prCur,v1000,fine,tool0;
        PrShift prCur;
        PrShift prCur;
        prY1:=prCur.trans.y;
        PrLift prCur,100;
        prY2:=prCur.trans.y;
        prZ:=prCur.trans.z;
        prX:=prCur.trans.x;
    ENDPROC

    PROC Probe()
        VAR iodev file;
        VAR num v;
        ConfJ\Off;
        ConfL\Off;
        PrProbe;
        Open "HOME:" \File:="pointrefprobe.txt", file \Write;
        v:=prY1;
        Write file, "prY1 " \Num:=v;
        v:=prY2;
        Write file, "prY2 " \Num:=v;
        v:=prZ;
        Write file, "prZ " \Num:=v;
        v:=prX;
        Write file, "prX " \Num:=v;
        v:=prSteps;
        Write file, "prSteps " \Num:=v;
        Close file;
    ENDPROC
ENDMODULE
