MODULE PinProbe
    ! CrossArm - pose probe. In RobotStudio, run PROC Probe (no motion): for every move of
    ! PROC Path it writes the flange pose in the world frame to HOME:/pinprobe.txt,
    ! as i x y z q1 q2 q3 q4. PROC Path is what CrossArm converts: never run it on a robot.
    PERS tooldata tProbeA:=[TRUE,[[30,-50,180],[1,0,0,0]],[1,[0,0,50],[1,0,0,0],0,0,0]];
    PERS tooldata tProbeB:=[TRUE,[[-40,25,220],[0.9659258,0,0.258819,0]],[1,[0,0,50],[1,0,0,0],0,0,0]];
    PERS tooldata tProbeC:=[TRUE,[[15,60,150],[0.6963642,-0.1227878,-0.1227878,0.6963642]],[1,[0,0,50],[1,0,0,0],0,0,0]];
    PERS wobjdata wProbe1:=[FALSE,TRUE,"",[[800,-350,150],[0.9659258,0,0,0.258819]],[[60,25,0],[1,0,0,0]]];
    PERS wobjdata wProbe2:=[FALSE,TRUE,"",[[950,250,300],[0.9757013,0.0340722,-0.0075536,-0.2163078]],[[0,0,40],[0.9914449,0,0,0.1305262]]];
    CONST robtarget pProbe1:=[[1070,-50,520],[0,0,-1,0],[-1,0,0,0],[9E+09,9E+09,9E+09,9E+09,9E+09,9E+09]];
    CONST robtarget pProbe2:=[[1029.037,-262.827,380],[0.254887,0.1677313,-0.9512512,0.0449435],[-1,0,0,0],[9E+09,9E+09,9E+09,9E+09,9E+09,9E+09]];
    CONST robtarget pProbe3:=[[284.179,-61.599,164.052],[0.0333531,0.3812272,0.9203639,0.0805214],[0,0,0,0],[9E+09,9E+09,9E+09,9E+09,9E+09,9E+09]];
    CONST robtarget pProbe4:=[[80.888,-141.301,154.884],[0.0560226,0.6403416,0.7631294,0.0667652],[0,0,0,0],[9E+09,9E+09,9E+09,9E+09,9E+09,9E+09]];
    CONST robtarget pProbe5:=[[88.988,76.287,83.554],[0.2576698,-0.1766274,-0.9498845,-0.011334],[0,0,0,0],[9E+09,9E+09,9E+09,9E+09,9E+09,9E+09]];
    CONST robtarget pProbe6:=[[218.586,-46.026,65.809],[0.0595245,0.6398023,0.7659193,0.0218514],[0,0,0,0],[9E+09,9E+09,9E+09,9E+09,9E+09,9E+09]];
    CONST robtarget pProbe7:=[[490.294,-52.682,28.662],[0.2659665,-0.1851027,-0.9457989,0.021522],[0,0,0,0],[9E+09,9E+09,9E+09,9E+09,9E+09,9E+09]];
    CONST robtarget pProbe8:=[[-46.535,157.865,220.839],[0.0257306,0.5369723,-0.8428777,0.0235778],[0,0,0,0],[9E+09,9E+09,9E+09,9E+09,9E+09,9E+09]];

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
        Open "HOME:" \File:="pinprobe.txt", f \Write;
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
        TPWrite "pinprobe.txt written in HOME:";
        Stop;
    ENDPROC

    PROC WriteFlange(num i,robtarget target,PERS tooldata tool,PERS wobjdata wobj)
        VAR iodev f;
        VAR pose tcp;
        VAR pose flange;
        tcp.trans:=target.trans;
        tcp.rot:=target.rot;
        flange:=PoseMult(PoseMult(PoseMult(wobj.uframe,wobj.oframe),tcp),PoseInv(tool.tframe));
        Open "HOME:" \File:="pinprobe.txt", f \Append;
        Write f, NumToStr(i,0)+" "+NumToStr(flange.trans.x,3)+" "+NumToStr(flange.trans.y,3)+" "+NumToStr(flange.trans.z,3)\NoNewLine;
        Write f, " "+NumToStr(flange.rot.q1,6)+" "+NumToStr(flange.rot.q2,6)+" "+NumToStr(flange.rot.q3,6)+" "+NumToStr(flange.rot.q4,6);
        Close f;
    ENDPROC
ENDMODULE
