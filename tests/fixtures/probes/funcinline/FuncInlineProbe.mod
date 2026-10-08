MODULE FuncInlineProbe
    ! CrossArm - FUNC inlining probe: see tools/make_func_inline_probe.py.
    PERS tooldata fiGrip:=[TRUE,[[0,0,100],[1,0,0,0]],[4,[0,0,50],[1,0,0,0],0,0,0]];
    PERS tooldata fiCam:=[TRUE,[[40,0,90],[1,0,0,0]],[1,[0,0,50],[1,0,0,0],0,0,0]];
    PERS wobjdata fiTable:=[FALSE,TRUE,"",[[1000,0,800],[0,0,1,0]],[[0,0,0],[1,0,0,0]]];
    CONST tooldata fiOfs1:=[TRUE,[[0,25,40],[1,0,0,0]],[0.5,[0,0,20],[1,0,0,0],0,0,0]];
    CONST tooldata fiOfs2:=[TRUE,[[0,-25,40],[1,0,0,0]],[0.5,[0,0,20],[1,0,0,0],0,0,0]];
    CONST tooldata fiOfs3:=[TRUE,[[30,0,62],[0.9659258,0.258819,0,0]],[0.5,[0,0,20],[1,0,0,0],0,0,0]];
    CONST tooldata fiOfs4:=[TRUE,[[20,0,30],[0.9238795,0,0.3826834,0]],[0.5,[0,0,20],[1,0,0,0],0,0,0]];
    CONST tooldata fiOfs5:=[TRUE,[[0,0,35],[1,0,0,0]],[0.5,[0,0,20],[1,0,0,0],0,0,0]];
    CONST tooldata fiOfs6:=[TRUE,[[15,0,20],[0.9396926,0,0,-0.3420201]],[0.5,[0,0,20],[1,0,0,0],0,0,0]];
    PERS tooldata fiT1:=[TRUE,[[0,0,200],[1,0,0,0]],[4.5,[0,0,50],[1,0,0,0],0,0,0]];
    PERS tooldata fiT2:=[TRUE,[[0,0,200],[1,0,0,0]],[4.5,[0,0,50],[1,0,0,0],0,0,0]];
    PERS tooldata fiT3:=[TRUE,[[0,0,200],[1,0,0,0]],[4.5,[0,0,50],[1,0,0,0],0,0,0]];
    PERS tooldata fiT4:=[TRUE,[[0,0,200],[1,0,0,0]],[4.5,[0,0,50],[1,0,0,0],0,0,0]];
    PERS tooldata fiHeavy:=[TRUE,[[0,0,200],[1,0,0,0]],[4.5,[0,0,50],[1,0,0,0],0,0,0]];
    PERS tooldata fiShift:=[TRUE,[[0,0,200],[1,0,0,0]],[4.5,[0,0,50],[1,0,0,0],0,0,0]];
    PERS tooldata fiT5:=[TRUE,[[0,0,200],[1,0,0,0]],[4.5,[0,0,50],[1,0,0,0],0,0,0]];
    PERS tooldata fiT6:=[TRUE,[[0,0,200],[1,0,0,0]],[4.5,[0,0,50],[1,0,0,0],0,0,0]];
    PERS tooldata fiTurn:=[TRUE,[[0,0,200],[1,0,0,0]],[4.5,[0,0,50],[1,0,0,0],0,0,0]];
    PERS wobjdata fiLeft:=[FALSE,TRUE,"",[[1000,0,800],[0,0,1,0]],[[0,0,0],[1,0,0,0]]];
    PERS wobjdata fiRight:=[FALSE,TRUE,"",[[1000,0,800],[0,0,1,0]],[[0,0,0],[1,0,0,0]]];
    CONST pose fiLeftOfs:=[[0,-150,0],[1,0,0,0]];
    CONST pose fiRightOfs:=[[0,150,0],[0.9961947,0,0,0.08715574]];
    CONST robtarget fiR1:=[[950,-60,820],[0,-0.1736482,0.9848078,0],[0,0,0,0],[9E9,9E9,9E9,9E9,9E9,9E9]];
    CONST robtarget fiR2:=[[1050,80,780],[0,0,1,0],[0,0,0,0],[9E9,9E9,9E9,9E9,9E9,9E9]];
    CONST robtarget fiDown:=[[1000,0,700],[0,-0.1736482,0.9848078,0],[0,0,0,0],[9E9,9E9,9E9,9E9,9E9,9E9]];
    CONST robtarget fiUp:=[[1000,0,700],[1,0,0,0],[0,0,0,0],[9E9,9E9,9E9,9E9,9E9,9E9]];
    CONST robtarget fiP:=[[40,30,-60],[1,0,0,0],[0,0,0,0],[9E9,9E9,9E9,9E9,9E9,9E9]];
    VAR robtarget fiM1;
    VAR robtarget fiM2;
    VAR robtarget fiG;
    VAR robtarget fiC;
    VAR robtarget fiF1;
    VAR robtarget fiF2;
    VAR robtarget fiF3;
    VAR robtarget fiF4;
    VAR robtarget fiF5;
    VAR robtarget fiF6;
    VAR robtarget fiF7;
    VAR robtarget fiF8;
    VAR robtarget fiF9;
    VAR robtarget fiF10;
    VAR robtarget fiF11;
    VAR num fiDone:=0;

    FUNC tooldata MakeTool(tooldata tBase,tooldata tOfs)
        VAR tooldata tRes;
        tRes:=tOfs;
        tRes.tframe:=PoseMult(tBase.tframe,tOfs.tframe);
        tRes.tload.mass:=tBase.tload.mass+tOfs.tload.mass;
        RETURN tRes;
    ENDFUNC

    FUNC tooldata WithLoad(tooldata tBase,num nMass)
        VAR tooldata tRes;
        tRes:=tBase;
        tRes.tload.mass:=nMass;
        RETURN tRes;
    ENDFUNC

    FUNC tooldata Shifted(tooldata tBase,num nDz)
        VAR tooldata tRes;
        tRes:=tBase;
        tRes.tframe.trans.z:=tBase.tframe.trans.z+nDz;
        RETURN tRes;
    ENDFUNC

    FUNC tooldata TurnTool(tooldata tBase,num nAngle)
        VAR pose peTurn;
        VAR tooldata tRes;
        peTurn:=[[0,0,0],OrientZYX(nAngle,0,0)];
        tRes:=tBase;
        tRes.tframe:=PoseMult(tBase.tframe,peTurn);
        RETURN tRes;
    ENDFUNC

    FUNC wobjdata ShiftFixture(wobjdata wBase,pose peShift)
        VAR wobjdata wRes;
        wRes:=wBase;
        wRes.uframe:=PoseMult(wBase.uframe,peShift);
        RETURN wRes;
    ENDFUNC

    PROC FiConv()
        fiDone:=0;
        FiCalib;
        FiInit;
        MoveJ fiDown,v500,fine,fiT1;
        fiF1:=CRobT(\Tool:=tool0\WObj:=wobj0);
        MoveJ fiDown,v500,fine,fiT2;
        fiF2:=CRobT(\Tool:=tool0\WObj:=wobj0);
        MoveJ fiDown,v500,fine,fiT3;
        fiF3:=CRobT(\Tool:=tool0\WObj:=wobj0);
        MoveJ fiDown,v500,fine,fiT4;
        fiF4:=CRobT(\Tool:=tool0\WObj:=wobj0);
        MoveJ fiDown,v500,fine,fiHeavy;
        fiF5:=CRobT(\Tool:=tool0\WObj:=wobj0);
        MoveJ fiDown,v500,fine,fiShift;
        fiF6:=CRobT(\Tool:=tool0\WObj:=wobj0);
        MoveJ fiUp,v500,fine,fiT5;
        fiF7:=CRobT(\Tool:=tool0\WObj:=wobj0);
        MoveJ fiUp,v500,fine,fiT6;
        fiF8:=CRobT(\Tool:=tool0\WObj:=wobj0);
        MoveJ fiUp,v500,fine,fiTurn;
        fiF9:=CRobT(\Tool:=tool0\WObj:=wobj0);
        MoveJ fiP,v500,fine,tool0\WObj:=fiLeft;
        fiF10:=CRobT(\Tool:=tool0\WObj:=wobj0);
        MoveJ fiP,v500,fine,tool0\WObj:=fiRight;
        fiF11:=CRobT(\Tool:=tool0\WObj:=wobj0);
        fiDone:=1;
    ENDPROC

    PROC FiCalib()
        MoveJ fiR2,v500,fine,tool0;
        fiM2:=CRobT(\Tool:=tool0\WObj:=wobj0);
        fiGrip.tframe.trans.x:=fiM2.trans.x-1040;
        fiGrip.tframe.trans.z:=fiM2.trans.z-640;
        MoveJ fiR1,v500,fine,tool0;
        fiM1:=CRobT(\Tool:=tool0\WObj:=wobj0);
        fiCam.tframe.trans.z:=fiM1.trans.z-700;
        fiCam.tframe.rot:=fiM1.rot;
        fiTable.uframe.trans:=fiM1.trans;
        fiTable.uframe.rot:=fiM1.rot;
        MoveJ fiDown,v500,fine,fiGrip;
        fiG:=CRobT(\Tool:=tool0\WObj:=wobj0);
        MoveJ fiUp,v500,fine,fiCam;
        fiC:=CRobT(\Tool:=tool0\WObj:=wobj0);
        MoveJ fiP,v500,fine,tool0\WObj:=fiTable;
    ENDPROC

    PROC FiInit()
        fiT1:=MakeTool(fiGrip,fiOfs1);
        fiT2:=MakeTool(fiGrip,fiOfs2);
        fiT3:=MakeTool(fiGrip,fiOfs3);
        fiT4:=MakeTool(fiGrip,fiOfs4);
        fiHeavy:=WithLoad(fiGrip,6);
        fiShift:=Shifted(fiGrip,25);
        fiT5:=MakeTool(fiCam,fiOfs5);
        fiT6:=MakeTool(fiCam,fiOfs6);
        fiTurn:=TurnTool(fiCam,-30);
        fiLeft:=ShiftFixture(fiTable,fiLeftOfs);
        fiRight:=ShiftFixture(fiTable,fiRightOfs);
    ENDPROC
ENDMODULE
