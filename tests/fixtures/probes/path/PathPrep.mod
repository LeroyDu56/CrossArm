MODULE PathPrep
    ! CrossArm - path probe, step 1: move to each point once and write it as reached (confdata
    ! included) to HOME:/pathprep.txt. Real motion: RobotStudio only.
    CONST jointtarget jStart:=[[0,0,0,0,90,45],[9E+09,9E+09,9E+09,9E+09,9E+09,9E+09]];
    CONST robtarget pTravel:=[[1100,-250,950],[0,0.3826834,0.9238795,0],[0,0,0,0],[9E+09,9E+09,9E+09,9E+09,9E+09,9E+09]];
    CONST robtarget pPick:=[[1300,100,700],[0,0.3826834,0.9238795,0],[0,0,0,0],[9E+09,9E+09,9E+09,9E+09,9E+09,9E+09]];
    CONST robtarget pAbove100:=[[1300,100,800],[0,0.3826834,0.9238795,0],[0,0,0,0],[9E+09,9E+09,9E+09,9E+09,9E+09,9E+09]];
    CONST robtarget pAbove50:=[[1300,100,750],[0,0.3826834,0.9238795,0],[0,0,0,0],[9E+09,9E+09,9E+09,9E+09,9E+09,9E+09]];
    CONST robtarget pAbove20:=[[1300,100,720],[0,0.3826834,0.9238795,0],[0,0,0,0],[9E+09,9E+09,9E+09,9E+09,9E+09,9E+09]];
    CONST robtarget pDownA:=[[1200,-150,1000],[0,0.3826834,0.9238795,0],[0,0,0,0],[9E+09,9E+09,9E+09,9E+09,9E+09,9E+09]];
    CONST robtarget pDownB:=[[1200,-150,800],[0,0.3826834,0.9238795,0],[0,0,0,0],[9E+09,9E+09,9E+09,9E+09,9E+09,9E+09]];
    CONST robtarget pDownC:=[[1200,-140,1000],[0,0.3826834,0.9238795,0],[0,0,0,0],[9E+09,9E+09,9E+09,9E+09,9E+09,9E+09]];
    CONST robtarget pTurnIn:=[[1250,-350,900],[0,0.3826834,0.9238795,0],[0,0,0,0],[9E+09,9E+09,9E+09,9E+09,9E+09,9E+09]];
    CONST robtarget pTurn:=[[1250,-50,900],[0,0.3826834,0.9238795,0],[0,0,0,0],[9E+09,9E+09,9E+09,9E+09,9E+09,9E+09]];
    CONST robtarget pTurn45:=[[1391.421,91.421,900],[0,0.3826834,0.9238795,0],[0,0,0,0],[9E+09,9E+09,9E+09,9E+09,9E+09,9E+09]];
    CONST robtarget pTurn135:=[[1391.421,-191.421,900],[0,0.3826834,0.9238795,0],[0,0,0,0],[9E+09,9E+09,9E+09,9E+09,9E+09,9E+09]];
    CONST robtarget pZig0:=[[1150,-100,800],[0,0.3826834,0.9238795,0],[0,0,0,0],[9E+09,9E+09,9E+09,9E+09,9E+09,9E+09]];
    CONST robtarget pZig1:=[[1200,-100,800],[0,0.3826834,0.9238795,0],[0,0,0,0],[9E+09,9E+09,9E+09,9E+09,9E+09,9E+09]];
    CONST robtarget pZig2:=[[1200,-50,800],[0,0.3826834,0.9238795,0],[0,0,0,0],[9E+09,9E+09,9E+09,9E+09,9E+09,9E+09]];
    CONST robtarget pZig3:=[[1250,-50,800],[0,0.3826834,0.9238795,0],[0,0,0,0],[9E+09,9E+09,9E+09,9E+09,9E+09,9E+09]];
    CONST robtarget pZig4:=[[1250,0,800],[0,0.3826834,0.9238795,0],[0,0,0,0],[9E+09,9E+09,9E+09,9E+09,9E+09,9E+09]];
    CONST robtarget pZig5:=[[1300,0,800],[0,0.3826834,0.9238795,0],[0,0,0,0],[9E+09,9E+09,9E+09,9E+09,9E+09,9E+09]];

    PROC Prep()
        VAR iodev f;
        Open "HOME:" \File:="pathprep.txt", f \Write;
        Close f;
        ConfJ\Off;
        ConfL\Off;
        MoveAbsJ jStart,v1000,fine,tool0;
        MoveJ pTravel,v1000,fine,tool0;
        Reached "pTravel";
        MoveJ pPick,v1000,fine,tool0;
        Reached "pPick";
        MoveJ pAbove100,v1000,fine,tool0;
        Reached "pAbove100";
        MoveJ pAbove50,v1000,fine,tool0;
        Reached "pAbove50";
        MoveJ pAbove20,v1000,fine,tool0;
        Reached "pAbove20";
        MoveJ pDownA,v1000,fine,tool0;
        Reached "pDownA";
        MoveJ pDownB,v1000,fine,tool0;
        Reached "pDownB";
        MoveJ pDownC,v1000,fine,tool0;
        Reached "pDownC";
        MoveJ pTurnIn,v1000,fine,tool0;
        Reached "pTurnIn";
        MoveJ pTurn,v1000,fine,tool0;
        Reached "pTurn";
        MoveJ pTurn45,v1000,fine,tool0;
        Reached "pTurn45";
        MoveJ pTurn135,v1000,fine,tool0;
        Reached "pTurn135";
        MoveJ pZig0,v1000,fine,tool0;
        Reached "pZig0";
        MoveJ pZig1,v1000,fine,tool0;
        Reached "pZig1";
        MoveJ pZig2,v1000,fine,tool0;
        Reached "pZig2";
        MoveJ pZig3,v1000,fine,tool0;
        Reached "pZig3";
        MoveJ pZig4,v1000,fine,tool0;
        Reached "pZig4";
        MoveJ pZig5,v1000,fine,tool0;
        Reached "pZig5";
        ConfJ\On;
        ConfL\On;
    ENDPROC

    PROC Reached(string name)
        VAR iodev f;
        VAR robtarget p;
        VAR jointtarget j;
        p:=CRobT(\Tool:=tool0\WObj:=wobj0);
        j:=CJointT();
        Open "HOME:" \File:="pathprep.txt", f \Append;
        Write f, name+" "+ValToStr(p.trans)+" "\NoNewLine;
        Write f, ValToStr(p.rot)+" "\NoNewLine;
        Write f, ValToStr(p.robconf)+" "\NoNewLine;
        Write f, ValToStr(j.robax);
        Close f;
    ENDPROC
ENDMODULE
