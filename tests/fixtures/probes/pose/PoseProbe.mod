MODULE PoseProbe
    ! CrossArm - pose probe. In RobotStudio, run PROC Probe (no motion): for every move of
    ! PROC Path it writes the flange pose in the world frame to HOME:/poseprobe.txt,
    ! as i x y z q1 q2 q3 q4. PROC Path is what CrossArm converts: never run it on a robot.
    PERS tooldata tProbeA:=[TRUE,[[30,-50,180],[1,0,0,0]],[1,[0,0,50],[1,0,0,0],0,0,0]];
    PERS tooldata tProbeB:=[TRUE,[[-40,25,220],[0.9659258,0,0.258819,0]],[1,[0,0,50],[1,0,0,0],0,0,0]];
    PERS tooldata tProbeC:=[TRUE,[[15,60,150],[0.6963642,-0.1227878,-0.1227878,0.6963642]],[1,[0,0,50],[1,0,0,0],0,0,0]];
    PERS wobjdata wProbe1:=[FALSE,TRUE,"",[[800,-350,150],[0.9659258,0,0,0.258819]],[[60,25,0],[1,0,0,0]]];
    PERS wobjdata wProbe2:=[FALSE,TRUE,"",[[950,250,300],[0.9757013,0.0340722,-0.0075536,-0.2163078]],[[0,0,40],[0.9914449,0,0,0.1305262]]];
    CONST robtarget pProbe1:=[[1130,50,520],[0,1,0,0],[0,0,0,0],[9E+09,9E+09,9E+09,9E+09,9E+09,9E+09]];
    CONST robtarget pProbe2:=[[970.963,-337.173,380],[0.0449435,-0.9512512,-0.1677313,-0.254887],[-1,0,0,0],[9E+09,9E+09,9E+09,9E+09,9E+09,9E+09]];
    CONST robtarget pProbe3:=[[396.242,-34.389,181.417],[0.0805214,-0.9203639,0.3812272,-0.0333531],[0,0,0,0],[9E+09,9E+09,9E+09,9E+09,9E+09,9E+09]];
    CONST robtarget pProbe4:=[[130.821,-254.348,149.674],[0.1982669,0.7399421,-0.6208852,-0.1663657],[0,0,0,0],[9E+09,9E+09,9E+09,9E+09,9E+09,9E+09]];
    CONST robtarget pProbe5:=[[-3.262,56.765,86.542],[0.0784981,0.951459,-0.1586308,0.2517937],[0,0,0,0],[9E+09,9E+09,9E+09,9E+09,9E+09,9E+09]];
    CONST robtarget pProbe6:=[[268.27,-159.301,66.308],[0.2414262,0.7272023,-0.6215761,-0.1628905],[0,0,0,0],[9E+09,9E+09,9E+09,9E+09,9E+09,9E+09]];
    CONST robtarget pProbe7:=[[398.184,-71.848,35.62],[0.1111899,0.9520691,-0.1495427,0.2425658],[0,0,0,0],[9E+09,9E+09,9E+09,9E+09,9E+09,9E+09]];
    CONST robtarget pProbe8:=[[-111.857,254.325,215.506],[0.0235778,0.8428777,0.5369723,-0.0257306],[0,0,0,0],[9E+09,9E+09,9E+09,9E+09,9E+09,9E+09]];

    PROC Path()
        MoveJ pProbe1,v200,fine,tProbeA\WObj:=wobj0;
        MoveJ pProbe2,v200,fine,tProbeB\WObj:=wobj0;
        MoveJ pProbe3,v200,fine,tProbeA\WObj:=wProbe1;
        MoveJ pProbe4,v200,fine,tProbeC\WObj:=wProbe1;
        MoveJ pProbe5,v200,fine,tProbeB\WObj:=wProbe2;
        MoveJ pProbe6,v200,fine,tProbeC\WObj:=wProbe2;
        MoveJ pProbe7,v200,fine,tProbeB\WObj:=wProbe1;
        MoveJ pProbe8,v200,fine,tProbeA\WObj:=wProbe2;
        MoveJ Offs(pProbe3,60,-40,30),v200,fine,tProbeA\WObj:=wProbe1;
        MoveJ Offs(pProbe5,-50,20,-35),v200,fine,tProbeB\WObj:=wProbe2;
        MoveJ RelTool(pProbe5,20,-30,40),v200,fine,tProbeB\WObj:=wProbe2;
        MoveJ RelTool(pProbe6,0,0,-50\Rz:=35),v200,fine,tProbeC\WObj:=wProbe2;
        MoveJ RelTool(pProbe2,10,10,10\Rx:=12\Ry:=-8\Rz:=20),v200,fine,tProbeB\WObj:=wobj0;
        MoveJ RelTool(pProbe4,0,0,0\Rx:=-15),v200,fine,tProbeC\WObj:=wProbe1;
        MoveJ Offs(RelTool(pProbe1,0,0,-40\Ry:=10),0,80,0),v200,fine,tProbeA\WObj:=wobj0;
        MoveJ pProbe1,v200,fine,tProbeC\WObj:=wobj0;
    ENDPROC

    PROC Probe()
        VAR iodev f;
        Open "HOME:" \File:="poseprobe.txt", f \Write;
        Close f;
        WriteFlange 1,pProbe1,tProbeA,wobj0;
        WriteFlange 2,pProbe2,tProbeB,wobj0;
        WriteFlange 3,pProbe3,tProbeA,wProbe1;
        WriteFlange 4,pProbe4,tProbeC,wProbe1;
        WriteFlange 5,pProbe5,tProbeB,wProbe2;
        WriteFlange 6,pProbe6,tProbeC,wProbe2;
        WriteFlange 7,pProbe7,tProbeB,wProbe1;
        WriteFlange 8,pProbe8,tProbeA,wProbe2;
        WriteFlange 9,Offs(pProbe3,60,-40,30),tProbeA,wProbe1;
        WriteFlange 10,Offs(pProbe5,-50,20,-35),tProbeB,wProbe2;
        WriteFlange 11,RelTool(pProbe5,20,-30,40),tProbeB,wProbe2;
        WriteFlange 12,RelTool(pProbe6,0,0,-50\Rz:=35),tProbeC,wProbe2;
        WriteFlange 13,RelTool(pProbe2,10,10,10\Rx:=12\Ry:=-8\Rz:=20),tProbeB,wobj0;
        WriteFlange 14,RelTool(pProbe4,0,0,0\Rx:=-15),tProbeC,wProbe1;
        WriteFlange 15,Offs(RelTool(pProbe1,0,0,-40\Ry:=10),0,80,0),tProbeA,wobj0;
        WriteFlange 16,pProbe1,tProbeC,wobj0;
        TPWrite "poseprobe.txt written in HOME:";
        Stop;
    ENDPROC

    PROC WriteFlange(num i,robtarget target,PERS tooldata tool,PERS wobjdata wobj)
        VAR iodev f;
        VAR pose tcp;
        VAR pose flange;
        tcp.trans:=target.trans;
        tcp.rot:=target.rot;
        flange:=PoseMult(PoseMult(PoseMult(wobj.uframe,wobj.oframe),tcp),PoseInv(tool.tframe));
        Open "HOME:" \File:="poseprobe.txt", f \Append;
        Write f, NumToStr(i,0)+" "+NumToStr(flange.trans.x,3)+" "+NumToStr(flange.trans.y,3)+" "+NumToStr(flange.trans.z,3)\NoNewLine;
        Write f, " "+NumToStr(flange.rot.q1,6)+" "+NumToStr(flange.rot.q2,6)+" "+NumToStr(flange.rot.q3,6)+" "+NumToStr(flange.rot.q4,6);
        Close f;
    ENDPROC
ENDMODULE
