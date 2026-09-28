MODULE BoundaryProbe
    ! CrossArm - J6 turn boundary probe: CrossArm converts PROC Path; the FANUC must reach every point.
    PERS tooldata tProbe:=[TRUE,[[0,0,200],[1,0,0,0]],[1,[0,0,50],[1,0,0,0],0,0,0]];
    CONST robtarget pAhead:=[[1300,0,900],[0,0,1,0],[0,0,0,0],[9E+09,9E+09,9E+09,9E+09,9E+09,9E+09]];
    CONST robtarget pAheadTool:=[[1300,0,700],[0,0,1,0],[0,0,0,0],[9E+09,9E+09,9E+09,9E+09,9E+09,9E+09]];
    CONST robtarget pAheadHigh:=[[1100,0,1000],[0,0,1,0],[0,0,0,0],[9E+09,9E+09,9E+09,9E+09,9E+09,9E+09]];
    CONST robtarget pTurned:=[[1300,0,900],[0,-0.0008727,0.9999996,0],[0,0,-1,0],[9E+09,9E+09,9E+09,9E+09,9E+09,9E+09]];
    CONST robtarget pTurnedBack:=[[1300,0,900],[0,0.0008727,0.9999996,0],[0,0,0,0],[9E+09,9E+09,9E+09,9E+09,9E+09,9E+09]];
    CONST robtarget pAside:=[[1126.333,650,900],[0,-0.258819,0.9659258,0],[0,0,-1,0],[9E+09,9E+09,9E+09,9E+09,9E+09,9E+09]];
    CONST robtarget pSide45:=[[1300,-300,900],[0,-0.3826834,0.9238795,0],[-1,0,-1,0],[9E+09,9E+09,9E+09,9E+09,9E+09,9E+09]];

    PROC Path()
        MoveJ pAhead,v500,fine,tool0;
        MoveJ pAheadTool,v500,fine,tProbe;
        MoveJ pAheadHigh,v500,fine,tool0;
        MoveJ pTurned,v500,fine,tool0;
        MoveJ pTurnedBack,v500,fine,tool0;
        MoveJ pAside,v500,fine,tool0;
        MoveJ pSide45,v500,fine,tool0;
    ENDPROC
ENDMODULE
