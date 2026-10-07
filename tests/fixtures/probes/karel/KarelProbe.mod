MODULE KarelProbe
    ! CrossArm - KAREL probe: see tools/make_karel_probe.py.
    VAR num krDone:=0;
    VAR num krX:=0;
    VAR num krY:=0;
    VAR pose krA;
    VAR pose krB;
    VAR pose krC;
    VAR pose krD;

    PROC KrProbe()
        krDone:=0;
        krX:=100;
        krY:=10;
        krA:=[[krX,-50,300],[0.8616424,0.2996729,-0.0574224,0.4055504]];
        krB:=[[krY,20,30],[0.7957964,0.2412865,0.2541212,-0.4938738]];
        krC:=PoseMult(krA,krB);
        krD:=PoseMult(krC,[[0,0,10],[0.7071068,0.0000000,0.0000000,0.7071068]]);
        krDone:=1;
    ENDPROC
ENDMODULE
