MODULE KarelPoseProbe
    ! CrossArm - KAREL pose probe: see tools/make_karel_pose_probe.py.
    PERS tooldata kpTool:=[TRUE,[[0,0,150],[0.9659258,0,0.258819,0]],[5,[0,0,50],[1,0,0,0],0,0,0]];
    PERS wobjdata kpWobj:=[FALSE,TRUE,"",[[1000,0,800],[1,0,0,0]],[[0,0,0],[1,0,0,0]]];
    CONST robtarget kpT1:=[[900,-100,800],[0,0,1,0],[0,0,0,0],[9E9,9E9,9E9,9E9,9E9,9E9]];
    CONST robtarget kpT2:=[[1100,50,820],[0,0,1,0],[0,0,0,0],[9E9,9E9,9E9,9E9,9E9,9E9]];
    CONST robtarget kpT3:=[[950,150,780],[0,0,1,0],[0,0,0,0],[9E9,9E9,9E9,9E9,9E9,9E9]];
    CONST robtarget kpP:=[[100,50,-50],[0,0,1,0],[0,0,0,0],[9E9,9E9,9E9,9E9,9E9,9E9]];
    VAR robtarget kpM1;
    VAR robtarget kpM2;
    VAR robtarget kpM3;
    VAR robtarget kpTurn;
    VAR robtarget kpF1;
    VAR robtarget kpF2;
    VAR robtarget kpF3;
    VAR pose kpCor;
    VAR num kpDone:=0;

    PROC KpConv()
        kpDone:=0;
        MoveJ kpT1,v500,fine,tool0;
        kpM1:=CRobT(\Tool:=tool0\WObj:=wobj0);
        MoveL kpT2,v500,fine,tool0;
        kpM2:=CRobT(\Tool:=tool0\WObj:=wobj0);
        MoveL kpT3,v500,fine,tool0;
        kpM3:=CRobT(\Tool:=tool0\WObj:=wobj0);
        kpWobj.uframe:=DefFrame(kpM1,kpM2,kpM3\Origin:=3);
        MoveL kpP,v500,fine,tool0\WObj:=kpWobj;
        kpF1:=CRobT(\Tool:=tool0\WObj:=wobj0);
        kpTurn:=RelTool(kpM2,0,0,-30\Rz:=-90);
        MoveL kpTurn,v500,fine,tool0;
        kpF2:=CRobT(\Tool:=tool0\WObj:=wobj0);
        kpCor:=[[kpM1.trans.x-900,kpM1.trans.y-(-100)+5,0],[1,0,0,0]];
        kpTool.tframe:=PoseMult(kpTool.tframe,PoseInv(kpCor));
        MoveL kpT1,v500,fine,kpTool;
        kpF3:=CRobT(\Tool:=tool0\WObj:=wobj0);
        kpDone:=1;
    ENDPROC
ENDMODULE
