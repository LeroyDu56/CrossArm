MODULE RtcpProbe
    ! CrossArm - remote TCP probe: see tools/make_rtcp_probe.py.
    PERS tooldata rtGun:=[FALSE,[[1300,50,700],[0.9659258,0,0,0.258819]],[1,[0,0,1],[1,0,0,0],0,0,0]];
    PERS wobjdata rtPart:=[TRUE,TRUE,"",[[10,-20,200],[0.9961947,0,0,0.08715574]],[[5,0,0],[0.9993908,0.0348995,0,0]]];
    CONST robtarget rtP1:=[[40,30,0],[0,0.1305262,0.9914449,0],[0,0,0,0],[9E9,9E9,9E9,9E9,9E9,9E9]];
    CONST robtarget rtP2:=[[-60,-20,5],[0.0226241,-0.2152539,0.9709478,-0.1020507],[0,0,0,0],[9E9,9E9,9E9,9E9,9E9,9E9]];
    CONST robtarget rtP3:=[[-40,-54.641,5],[0.08715574,0,0.9961947,0],[0,0,0,0],[9E9,9E9,9E9,9E9,9E9,9E9]];
    CONST robtarget rtP4:=[[0,-54.641,5],[0,0.1736482,0.9848078,0],[0,0,0,0],[9E9,9E9,9E9,9E9,9E9,9E9]];
    VAR robtarget rtF1;
    VAR robtarget rtF2;
    VAR robtarget rtF4;
    VAR robtarget rtF5;
    VAR num rtDone:=0;

    PROC RtPrep()
        MoveJ rtP1,v500,fine,rtGun\WObj:=rtPart;
        rtF1:=CRobT(\Tool:=tool0\WObj:=wobj0);
    ENDPROC

    PROC RtConv()
        rtDone:=0;
        MoveL rtP2,v20,fine,rtGun\WObj:=rtPart;
        rtF2:=CRobT(\Tool:=tool0\WObj:=wobj0);
        MoveC rtP3,rtP4,v20,fine,rtGun\WObj:=rtPart;
        rtF4:=CRobT(\Tool:=tool0\WObj:=wobj0);
        MoveL Offs(rtP1,0,0,8),v20,z5,rtGun\WObj:=rtPart;
        MoveL rtP1,v20,fine,rtGun\WObj:=rtPart;
        rtF5:=CRobT(\Tool:=tool0\WObj:=wobj0);
        rtDone:=1;
    ENDPROC
ENDMODULE
