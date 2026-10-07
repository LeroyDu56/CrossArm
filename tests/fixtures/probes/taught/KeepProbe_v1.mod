MODULE KeepProbe
    ! CrossArm - taught positions probe, version 1: see tools/make_taught_probe.py.
    PERS tooldata tKeep:=[TRUE,[[0,0,150],[1,0,0,0]],[2,[0,0,60],[1,0,0,0],0,0,0]];
    PERS wobjdata wKeep:=[FALSE,TRUE,"",[[900,0,400],[1,0,0,0]],[[0,0,0],[1,0,0,0]]];
    CONST robtarget pKeep:=[[100,-150,200],[0,0,1,0],[0,0,0,0],[9E+09,9E+09,9E+09,9E+09,9E+09,9E+09]];
    CONST robtarget pMove:=[[150,100,200],[0,0,1,0],[0,0,0,0],[9E+09,9E+09,9E+09,9E+09,9E+09,9E+09]];
    CONST robtarget pPlain:=[[-50,0,250],[0,0,1,0],[0,0,0,0],[9E+09,9E+09,9E+09,9E+09,9E+09,9E+09]];

    PROC KeepProbe()
        MoveL pKeep,v200,fine,tKeep\WObj:=wKeep;
        MoveL pMove,v200,fine,tKeep\WObj:=wKeep;
        MoveL pPlain,v200,fine,tKeep\WObj:=wKeep;
    ENDPROC
ENDMODULE
