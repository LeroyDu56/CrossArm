MODULE ComputeProbe
    ! CrossArm - compute probe. In RobotStudio, run PROC Probe (no motion): it does what PROC Path does and
    ! writes, for each move, the flange pose in the world frame to HOME:/computeprobe.txt as
    ! i x y z q1 q2 q3 q4. PROC Path is what CrossArm converts: never run it on a robot.
    RECORD shiftdata
        num rz;
        pos offset;
    ENDRECORD

    PERS tooldata tBase:=[TRUE,[[20,-30,200],[1,0,0,0]],[5,[0,0,80],[1,0,0,0],0,0,0]];
    PERS tooldata tBuilt:=[TRUE,[[0,0,100],[1,0,0,0]],[5,[0,0,80],[1,0,0,0],0,0,0]];
    PERS tooldata tFixed:=[FALSE,[[1500,0,400],[1,0,0,0]],[1,[0,0,0],[1,0,0,0],0,0,0]];
    PERS shiftdata sShift:=[25,[15,-10,40]];
    PERS wobjdata wBase:=[FALSE,TRUE,"",[[900,-200,100],[0.9723323,-0.0774561,0.0273980,0.2186775]],[[30,20,0],[1,0,0,0]]];
    PERS wobjdata wCopy:=[FALSE,TRUE,"",[[0,0,0],[1,0,0,0]],[[0,0,50],[0.9961947,0,0,-0.0871557]]];
    PERS wobjdata wDef:=[FALSE,TRUE,"",[[0,0,0],[1,0,0,0]],[[0,0,0],[1,0,0,0]]];
    CONST robtarget pD1:=[[950,-150,120],[1,0,0,0],[0,0,0,0],[9E+09,9E+09,9E+09,9E+09,9E+09,9E+09]];
    CONST robtarget pD2:=[[1150,-50,110],[1,0,0,0],[0,0,0,0],[9E+09,9E+09,9E+09,9E+09,9E+09,9E+09]];
    CONST robtarget pD3:=[[1000,100,140],[1,0,0,0],[0,0,0,0],[9E+09,9E+09,9E+09,9E+09,9E+09,9E+09]];
    CONST robtarget pT1:=[[1100,50,500],[0,1,0,0],[0,0,0,0],[9E+09,9E+09,9E+09,9E+09,9E+09,9E+09]];
    CONST robtarget pT2:=[[200,100,300],[0,1,0,0],[0,0,0,0],[9E+09,9E+09,9E+09,9E+09,9E+09,9E+09]];
    CONST robtarget pT3:=[[100,50,350],[0,1,0,0],[0,0,0,0],[9E+09,9E+09,9E+09,9E+09,9E+09,9E+09]];
    CONST robtarget pT4:=[[0,0,0],[1,0,0,0],[0,0,0,0],[9E+09,9E+09,9E+09,9E+09,9E+09,9E+09]];
    CONST jointtarget jPark:=[[10,-10,10,0,60,30],[9E+09,9E+09,9E+09,9E+09,9E+09,9E+09]];

    FUNC tooldata MakeTool(tooldata base,shiftdata shift)
        VAR tooldata t;
        VAR pose p;
        t:=base;
        p.trans:=shift.offset;
        p.rot:=OrientZYX(shift.rz,0,0);
        t.tframe:=PoseMult(base.tframe,p);
        RETURN t;
    ENDFUNC

    PROC Path()
        VAR robtarget pC;
        tBuilt:=MakeTool(tBase,sShift);
        MoveJ pT1,v200,fine,tBuilt\WObj:=wobj0;
        wCopy.uframe:=wBase.uframe;
        MoveJ pT2,v200,fine,tBuilt\WObj:=wCopy;
        wDef.uframe:=DefFrame(pD1,pD2,pD3);
        MoveJ pT3,v200,fine,tBase\WObj:=wDef;
        wDef.uframe:=DefFrame(pD1,pD2,pD3\Origin:=2);
        MoveJ pT3,v200,fine,tBase\WObj:=wDef;
        wDef.uframe:=DefFrame(pD1,pD2,pD3\Origin:=3);
        MoveJ pT3,v200,fine,tBase\WObj:=wDef;
        pC:=pT4;
        pC.trans:=PoseVect(PoseInv([[-1000,200,-600],[1,0,0,0]]),[70,-20,0]);
        pC.rot:=OrientZYX(EulerZYX(\Z,wBase.uframe.rot),EulerZYX(\Y,wBase.uframe.rot),180+EulerZYX(\X,wBase.uframe.rot));
        MoveJ pC,v200,fine,tBase\WObj:=wobj0;
        MoveJ RelTool(pC,0,0,-50\Rz:=20),v200,fine,tBase\WObj:=wobj0;
        tBuilt:=MakeTool(tBase,[-40,[0,25,-30]]);
        MoveJ pT1,v200,fine,tBuilt\WObj:=wobj0;
        MoveAbsJ jPark,v200,fine,tFixed;
        wDef.uframe:=DefFrame(pD1,pD2,pD3);
        MoveJ pT3,v200,fine,tBase\WObj:=wDef;
    ENDPROC

    PROC Probe()
        VAR robtarget pC;
        VAR iodev f;
        Open "HOME:" \File:="computeprobe.txt", f \Write;
        Close f;
        tBuilt:=MakeTool(tBase,sShift);
        WriteFlange 1,pT1,tBuilt,wobj0;
        wCopy.uframe:=wBase.uframe;
        WriteFlange 2,pT2,tBuilt,wCopy;
        wDef.uframe:=DefFrame(pD1,pD2,pD3);
        WriteFlange 3,pT3,tBase,wDef;
        wDef.uframe:=DefFrame(pD1,pD2,pD3\Origin:=2);
        WriteFlange 4,pT3,tBase,wDef;
        wDef.uframe:=DefFrame(pD1,pD2,pD3\Origin:=3);
        WriteFlange 5,pT3,tBase,wDef;
        pC:=pT4;
        pC.trans:=PoseVect(PoseInv([[-1000,200,-600],[1,0,0,0]]),[70,-20,0]);
        pC.rot:=OrientZYX(EulerZYX(\Z,wBase.uframe.rot),EulerZYX(\Y,wBase.uframe.rot),180+EulerZYX(\X,wBase.uframe.rot));
        WriteFlange 6,pC,tBase,wobj0;
        WriteFlange 7,RelTool(pC,0,0,-50\Rz:=20),tBase,wobj0;
        tBuilt:=MakeTool(tBase,[-40,[0,25,-30]]);
        WriteFlange 8,pT1,tBuilt,wobj0;
        ! move 9: a joint target, not compared
        wDef.uframe:=DefFrame(pD1,pD2,pD3);
        WriteFlange 10,pT3,tBase,wDef;
        TPWrite "computeprobe.txt written in HOME:";
        Stop;
    ENDPROC

    PROC WriteFlange(num i,robtarget target,PERS tooldata tool,PERS wobjdata wobj)
        VAR iodev f;
        VAR pose tcp;
        VAR pose flange;
        tcp.trans:=target.trans;
        tcp.rot:=target.rot;
        flange:=PoseMult(PoseMult(PoseMult(wobj.uframe,wobj.oframe),tcp),PoseInv(tool.tframe));
        Open "HOME:" \File:="computeprobe.txt", f \Append;
        Write f, NumToStr(i,0)+" "+NumToStr(flange.trans.x,3)+" "+NumToStr(flange.trans.y,3)+" "+NumToStr(flange.trans.z,3)\NoNewLine;
        Write f, " "+NumToStr(flange.rot.q1,6)+" "+NumToStr(flange.rot.q2,6)+" "+NumToStr(flange.rot.q3,6)+" "+NumToStr(flange.rot.q4,6);
        Close f;
    ENDPROC
ENDMODULE
