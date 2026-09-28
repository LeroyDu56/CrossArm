MODULE BoundaryPrep
    PERS tooldata tProbe:=[TRUE,[[0,0,200],[1,0,0,0]],[1,[0,0,50],[1,0,0,0],0,0,0]];
    CONST robtarget pAhead:=[[1300,0,900],[0,0,1,0],[0,0,0,0],[9E+09,9E+09,9E+09,9E+09,9E+09,9E+09]];
    CONST robtarget pAheadTool:=[[1300,0,700],[0,0,1,0],[0,0,0,0],[9E+09,9E+09,9E+09,9E+09,9E+09,9E+09]];
    CONST robtarget pAheadHigh:=[[1100,0,1000],[0,0,1,0],[0,0,0,0],[9E+09,9E+09,9E+09,9E+09,9E+09,9E+09]];
    CONST robtarget pTurned:=[[1300,0,900],[0,-0.0008727,0.9999996,0],[0,0,0,0],[9E+09,9E+09,9E+09,9E+09,9E+09,9E+09]];
    CONST robtarget pTurnedBack:=[[1300,0,900],[0,0.0008727,0.9999996,0],[0,0,0,0],[9E+09,9E+09,9E+09,9E+09,9E+09,9E+09]];
    CONST robtarget pAside:=[[1126.333,650,900],[0,-0.258819,0.9659258,0],[0,0,0,0],[9E+09,9E+09,9E+09,9E+09,9E+09,9E+09]];
    CONST robtarget pSide45:=[[1300,-300,900],[0,-0.3826834,0.9238795,0],[0,0,0,0],[9E+09,9E+09,9E+09,9E+09,9E+09,9E+09]];

    PROC Prep()
        VAR iodev f;
        Open "HOME:" \File:="boundaryprep.txt", f \Write;
        Close f;
        ConfJ\Off;
        MoveJ pAhead,v1000,fine,tool0;
        Reached "pAhead",tool0;
        MoveJ pAheadTool,v1000,fine,tProbe;
        Reached "pAheadTool",tProbe;
        MoveJ pAheadHigh,v1000,fine,tool0;
        Reached "pAheadHigh",tool0;
        MoveJ pTurned,v1000,fine,tool0;
        Reached "pTurned",tool0;
        MoveJ pTurnedBack,v1000,fine,tool0;
        Reached "pTurnedBack",tool0;
        MoveJ pAside,v1000,fine,tool0;
        Reached "pAside",tool0;
        MoveJ pSide45,v1000,fine,tool0;
        Reached "pSide45",tool0;
        ConfJ\On;
    ENDPROC

    PROC Reached(string name,PERS tooldata tool)
        VAR iodev f;
        VAR robtarget p;
        VAR jointtarget j;
        p:=CRobT(\Tool:=tool\WObj:=wobj0);
        j:=CJointT();
        Open "HOME:" \File:="boundaryprep.txt", f \Append;
        Write f, name+" "+ValToStr(p.robconf)+" "+NumToStr(j.robax.rax_6,4);
        Close f;
    ENDPROC
ENDMODULE
