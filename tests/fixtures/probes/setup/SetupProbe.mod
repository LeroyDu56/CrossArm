MODULE SetupProbe
    ! CrossArm - setup probe. Only converted by CrossArm, never run: see tools/make_setup_probe.py.
    PERS tooldata tSetA:=[TRUE,[[12.5,-7.25,241],[1,0,0,0]],[1,[0,0,50],[1,0,0,0],0,0,0]];
    PERS tooldata tSetB:=[TRUE,[[-55,33,160.4],[0.9238795,0,0.3826834,0]],[1,[0,0,50],[1,0,0,0],0,0,0]];
    PERS tooldata tSetC:=[TRUE,[[80,90,95],[0.8660254,0.2588190,0,0.4267767]],[1,[0,0,50],[1,0,0,0],0,0,0]];
    PERS wobjdata wSet1:=[FALSE,TRUE,"",[[640,-420,85],[0.9848078,0,0,-0.1736482]],[[0,0,0],[1,0,0,0]]];
    PERS wobjdata wSet2:=[FALSE,TRUE,"",[[1020,310,-40],[0.9961947,0.0871557,0,0]],[[35,-15,20],[0.9659258,0,0,0.258819]]];
    CONST robtarget pSet:=[[0,0,0],[0,0,1,0],[0,0,0,0],[9E+09,9E+09,9E+09,9E+09,9E+09,9E+09]];
    PROC main()
        MoveJ pSet,v100,fine,tSetA\WObj:=wSet1;
        MoveJ pSet,v100,fine,tSetB\WObj:=wSet2;
        MoveJ pSet,v100,fine,tSetC;
    ENDPROC
ENDMODULE
