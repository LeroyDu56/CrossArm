MODULE FuncResultProbe
    ! CrossArm - provided functions probe: see tools/make_func_result_probe.py.
    PERS tooldata frProbe:=[TRUE,[[0,0,150],[1,0,0,0]],[3,[0,0,50],[1,0,0,0],0,0,0]];
    PERS wobjdata frHub:=[FALSE,TRUE,"",[[1000,0,800],[0,0,1,0]],[[0,0,0],[1,0,0,0]]];
    PERS wobjdata frRing:=[FALSE,TRUE,"",[[1000,0,800],[0,0,1,0]],[[0,0,0],[1,0,0,0]]];
    CONST robtarget frA:=[[1000,-40,800],[0,0,1,0],[0,0,0,0],[9E9,9E9,9E9,9E9,9E9,9E9]];
    CONST robtarget frB:=[[1060,40,800],[0,0,1,0],[0,0,0,0],[9E9,9E9,9E9,9E9,9E9,9E9]];
    CONST robtarget frP:=[[40,30,-60],[1,0,0,0],[0,0,0,0],[9E9,9E9,9E9,9E9,9E9,9E9]];
    VAR robtarget frM1;
    VAR robtarget frM2;
    VAR robtarget frMid;
    VAR robtarget frF1;
    VAR robtarget frF2;
    VAR robtarget frF3;
    VAR robtarget frF4;
    VAR num frGap:=0;
    VAR num frDone:=0;

    PROC FrConv()
        frDone:=0;
        MoveJ frA,v500,fine,tool0;
        frM1:=CRobT(\Tool:=tool0\WObj:=wobj0);
        MoveL frB,v500,fine,tool0;
        frM2:=CRobT(\Tool:=tool0\WObj:=wobj0);
        frGap:=FrGap(frM1,frM2);
        frMid:=FrMid(frM1,frM2);
        MoveL frMid,v500,fine,tool0;
        frF1:=CRobT(\Tool:=tool0\WObj:=wobj0);
        frHub.uframe.trans:=frMid.trans;
        MoveL frP,v500,fine,tool0\WObj:=frHub;
        frF2:=CRobT(\Tool:=tool0\WObj:=wobj0);
        frRing.uframe:=FrFit(frA,frB,frGap);
        MoveL frP,v500,fine,tool0\WObj:=frRing;
        frF3:=CRobT(\Tool:=tool0\WObj:=wobj0);
        frProbe.tframe.trans:=FrOffset(2);
        MoveL frB,v500,fine,frProbe;
        frF4:=CRobT(\Tool:=tool0\WObj:=wobj0);
        frDone:=1;
    ENDPROC
ENDMODULE
