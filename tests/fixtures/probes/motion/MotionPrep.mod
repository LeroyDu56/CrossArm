MODULE MotionPrep
    ! CrossArm - motion probe, step 1: move to each point once and write it as reached (confdata
    ! included) to HOME:/motionprep.txt. Real motion: RobotStudio only.
    CONST jointtarget jStart:=[[0,0,0,0,90,45],[9E+09,9E+09,9E+09,9E+09,9E+09,9E+09]];
    CONST robtarget pCornerA:=[[1100,-200,800],[0,0.3826834,0.9238795,0],[0,0,0,0],[9E+09,9E+09,9E+09,9E+09,9E+09,9E+09]];
    CONST robtarget pCornerB:=[[1400,-200,800],[0,0.3826834,0.9238795,0],[0,0,0,0],[9E+09,9E+09,9E+09,9E+09,9E+09,9E+09]];
    CONST robtarget pCornerC:=[[1400,200,800],[0,0.3826834,0.9238795,0],[0,0,0,0],[9E+09,9E+09,9E+09,9E+09,9E+09,9E+09]];
    CONST robtarget pLineA:=[[1100,-300,800],[0,0.3826834,0.9238795,0],[0,0,0,0],[9E+09,9E+09,9E+09,9E+09,9E+09,9E+09]];
    CONST robtarget pLineB:=[[1100,300,800],[0,0.3826834,0.9238795,0],[0,0,0,0],[9E+09,9E+09,9E+09,9E+09,9E+09,9E+09]];
    CONST robtarget pJointA:=[[1100,-400,600],[0,0.3826834,0.9238795,0],[0,0,0,0],[9E+09,9E+09,9E+09,9E+09,9E+09,9E+09]];
    CONST robtarget pJointB:=[[1400,300,1000],[0,0.3826834,0.9238795,0],[0,0,0,0],[9E+09,9E+09,9E+09,9E+09,9E+09,9E+09]];
    CONST robtarget pSwingA:=[[1100,-500,800],[0,0.3826834,0.9238795,0],[0,0,0,0],[9E+09,9E+09,9E+09,9E+09,9E+09,9E+09]];
    CONST robtarget pSwingB:=[[1100,500,800],[0,0.3826834,0.9238795,0],[0,0,0,0],[9E+09,9E+09,9E+09,9E+09,9E+09,9E+09]];
    CONST robtarget pRiseA:=[[1250,0,500],[0,0.3826834,0.9238795,0],[0,0,0,0],[9E+09,9E+09,9E+09,9E+09,9E+09,9E+09]];
    CONST robtarget pRiseB:=[[1250,0,1100],[0,0.3826834,0.9238795,0],[0,0,0,0],[9E+09,9E+09,9E+09,9E+09,9E+09,9E+09]];

    PROC Prep()
        VAR iodev f;
        Open "HOME:" \File:="motionprep.txt", f \Write;
        Close f;
        ConfJ\Off;
        ConfL\Off;
        MoveAbsJ jStart,v1000,fine,tool0;
        MoveJ pCornerA,v1000,fine,tool0;
        Reached "pCornerA";
        MoveJ pCornerB,v1000,fine,tool0;
        Reached "pCornerB";
        MoveJ pCornerC,v1000,fine,tool0;
        Reached "pCornerC";
        MoveJ pLineA,v1000,fine,tool0;
        Reached "pLineA";
        MoveJ pLineB,v1000,fine,tool0;
        Reached "pLineB";
        MoveJ pJointA,v1000,fine,tool0;
        Reached "pJointA";
        MoveJ pJointB,v1000,fine,tool0;
        Reached "pJointB";
        MoveJ pSwingA,v1000,fine,tool0;
        Reached "pSwingA";
        MoveJ pSwingB,v1000,fine,tool0;
        Reached "pSwingB";
        MoveJ pRiseA,v1000,fine,tool0;
        Reached "pRiseA";
        MoveJ pRiseB,v1000,fine,tool0;
        Reached "pRiseB";
        ConfJ\On;
        ConfL\On;
    ENDPROC

    PROC Reached(string name)
        VAR iodev f;
        VAR robtarget p;
        VAR jointtarget j;
        p:=CRobT(\Tool:=tool0\WObj:=wobj0);
        j:=CJointT();
        Open "HOME:" \File:="motionprep.txt", f \Append;
        Write f, name+" "+ValToStr(p.trans)+" "\NoNewLine;
        Write f, ValToStr(p.rot)+" "\NoNewLine;
        Write f, ValToStr(p.robconf)+" "\NoNewLine;
        Write f, ValToStr(j.robax);
        Close f;
    ENDPROC
ENDMODULE
