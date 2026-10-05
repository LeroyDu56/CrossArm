MODULE SearchProbe
    ! CrossArm - search probe: see tools/make_search_probe.py.
    CONST robtarget pStart:=[[1100,50,1000],[0,1,0,0],[0,0,0,0],[9E+09,9E+09,9E+09,9E+09,9E+09,9E+09]];
    CONST robtarget pEnd:=[[1100,250,1000],[0,1,0,0],[0,0,0,0],[9E+09,9E+09,9E+09,9E+09,9E+09,9E+09]];
    VAR robtarget pFound;
    VAR robtarget pAt;
    VAR num nFoundY:=0;
    VAR num nStopY:=0;
    VAR num nOffsY:=0;
    VAR num nOffsZ:=0;
    VAR num nSupFoundY:=0;
    VAR num nSupEndY:=0;

    PROC SpStop()
        MoveJ pStart,v1000,fine,tool0;
        SearchL\Stop,diProbe,pFound,pEnd,v50,tool0;
        nFoundY:=pFound.trans.y;
        pAt:=CRobT(\Tool:=tool0\WObj:=wobj0);
        nStopY:=pAt.trans.y;
        MoveL Offs(pFound,0,0,50),v100,fine,tool0;
        pAt:=CRobT(\Tool:=tool0\WObj:=wobj0);
        nOffsY:=pAt.trans.y;
        nOffsZ:=pAt.trans.z;
    ENDPROC

    PROC SpSup()
        MoveJ pStart,v1000,fine,tool0;
        SearchL\Sup,diProbe,pFound,pEnd,v50,tool0;
        nSupFoundY:=pFound.trans.y;
        pAt:=CRobT(\Tool:=tool0\WObj:=wobj0);
        nSupEndY:=pAt.trans.y;
    ENDPROC

    PROC SpEarly()
        MoveJ pStart,v1000,fine,tool0;
        SearchL\Stop,diProbe,pFound,pEnd,v50,tool0;
    ENDPROC
ENDMODULE
