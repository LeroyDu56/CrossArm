MODULE ToolArgProbe
    ! CrossArm - tool argument probe: see tools/make_tool_arg_probe.py.
    PERS tooldata taPen:=[TRUE,[[0,0,100],[1,0,0,0]],[2,[0,0,50],[1,0,0,0],0,0,0]];
    PERS tooldata taCup:=[TRUE,[[20,0,140],[0.9659258,0,0.258819,0]],[2,[0,0,50],[1,0,0,0],0,0,0]];
    CONST robtarget taP1:=[[1000,0,800],[0,0,1,0],[0,0,0,0],[9E9,9E9,9E9,9E9,9E9,9E9]];
    CONST robtarget taP2:=[[1050,80,760],[0,-0.2164396,0.976296,0],[0,0,0,0],[9E9,9E9,9E9,9E9,9E9,9E9]];
    CONST robtarget taP3:=[[980,-90,840],[0,0,1,0],[0,0,0,0],[9E9,9E9,9E9,9E9,9E9,9E9]];
    VAR robtarget taM;
    VAR robtarget taCopy;
    VAR robtarget taF1;
    VAR robtarget taF2;
    VAR robtarget taF3;
    VAR robtarget taF4;
    VAR num taLen:=0;
    VAR bool taOk:=FALSE;
    VAR num taOk1:=0;
    VAR num taOk2:=0;
    VAR num taDone:=0;

    PROC TaConv()
        taDone:=0;
        MoveJ taP1,v500,fine,tool0;
        taM:=CRobT(\Tool:=tool0\WObj:=wobj0);
        taLen:=taM.trans.z-650;
        TaLength taPen,taLen;
        TaLength taCup,taLen+30;
        MoveL taP2,v500,fine,taPen;
        taF1:=CRobT(\Tool:=tool0\WObj:=wobj0);
        MoveL taP2,v500,fine,taCup;
        taF2:=CRobT(\Tool:=tool0\WObj:=wobj0);
        taOk:=FALSE;
        TaCheck taLen,taOk\Pt:=taP3;
        taF3:=CRobT(\Tool:=tool0\WObj:=wobj0);
        IF taOk THEN
            taOk1:=1;
        ELSE
            taOk1:=2;
        ENDIF
        TaCheck taLen+1000,taOk;
        IF taOk THEN
            taOk2:=1;
        ELSE
            taOk2:=2;
        ENDIF
        taCopy:=taF3;
        taCopy.trans:=taF1.trans;
        taCopy.rot:=taF2.rot;
        MoveL taCopy,v500,fine,tool0;
        taF4:=CRobT(\Tool:=tool0\WObj:=wobj0);
        taDone:=1;
    ENDPROC

    PROC TaLength(INOUT tooldata t,num nLen)
        t.tframe.trans.z:=nLen;
        t.tframe.rot:=[1,0,0,0];
    ENDPROC

    PROC TaCheck(num nLim,INOUT bool bOk\robtarget Pt)
        IF Present(Pt) MoveL Pt,v500,fine,tool0;
        bOk:=nLim<500;
    ENDPROC
ENDMODULE
