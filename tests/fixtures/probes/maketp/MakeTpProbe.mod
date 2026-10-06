MODULE MakeTpProbe
    ! CrossArm - MakeTP probe: see tools/make_maketp_probe.py.
    VAR num mtSum:=0;
    VAR num mtCalls:=0;
    VAR num mtFlag:=0;
    PERS tooldata tMkTp:=[TRUE,[[0,0,150],[1,0,0,0]],[2,[0,0,60],[1,0,0,0],0,0,0]];
    PERS wobjdata wMkTp:=[FALSE,TRUE,"",[[900,0,400],[1,0,0,0]],[[0,0,0],[1,0,0,0]]];
    CONST jointtarget jMkTp:=[[0,0,0,0,-90,0],[9E+09,9E+09,9E+09,9E+09,9E+09,9E+09]];
    CONST robtarget pMkTp:=[[0,0,0],[0,0,1,0],[0,0,0,0],[9E+09,9E+09,9E+09,9E+09,9E+09,9E+09]];

    PROC MtProbe()
        mtSum:=0;
        mtCalls:=0;
        mtFlag:=0;
        MoveAbsJ jMkTp,v1000,fine,tool0;
        FOR i FROM 1 TO 5 DO
            mtSum:=mtSum+i*2;
            MtCount;
        ENDFOR
        IF mtSum=30 mtFlag:=100;
    ENDPROC

    PROC MtCount()
        mtCalls:=mtCalls+1;
    ENDPROC

    PROC MtTeach()
        MoveL pMkTp,v200,fine,tMkTp\WObj:=wMkTp;
    ENDPROC
ENDMODULE
