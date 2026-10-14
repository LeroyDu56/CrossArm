MODULE WaitProbe
    ! CrossArm - WaitRob probe: see tools/make_waitrob_probe.py.
    CONST robtarget wpStart:=[[1100,-200,800],[0,0.3826834,0.9238795,0],[-1,0,0,0],[9E+09,9E+09,9E+09,9E+09,9E+09,9E+09]];
    CONST robtarget wpCorner:=[[1400,-200,800],[0,0.3826834,0.9238795,0],[-1,0,0,0],[9E+09,9E+09,9E+09,9E+09,9E+09,9E+09]];
    CONST robtarget wpEnd:=[[1400,200,800],[0,0.3826834,0.9238795,0],[0,0,0,0],[9E+09,9E+09,9E+09,9E+09,9E+09,9E+09]];
    VAR robtarget wpNoWait;
    VAR robtarget wpInPos;
    VAR robtarget wpZeroSpeed;
    VAR num nDone:=0;

    PROC WaitProbe()
        nDone:=0;
        MoveJ wpStart,v1000,fine,tool0;
        MoveL wpCorner,v100,z100,tool0;
        wpNoWait:=CRobT(\Tool:=tool0\WObj:=wobj0);
        MoveL wpStart,v1000,fine,tool0;
        MoveL wpCorner,v100,z100,tool0;
        WaitRob\InPos;
        wpInPos:=CRobT(\Tool:=tool0\WObj:=wobj0);
        MoveL wpStart,v1000,fine,tool0;
        ToCorner;
        WaitRob\ZeroSpeed;
        wpZeroSpeed:=CRobT(\Tool:=tool0\WObj:=wobj0);
        MoveL wpEnd,v100,fine,tool0;
        nDone:=1;
    ENDPROC

    PROC ToCorner()
        MoveL wpCorner,v100,z100,tool0;
    ENDPROC
ENDMODULE
