MODULE BranchFrameProbe
    ! CrossArm - branch frame probe: see tools/make_branch_frame_probe.py.
    PERS wobjdata bfSideA:=[FALSE,TRUE,"",[[1000,-100,700],[1,0,0,0]],[[0,0,0],[1,0,0,0]]];
    PERS wobjdata bfSideB:=[FALSE,TRUE,"",[[1100,100,700],[0.7071068,0,0,0.7071068]],[[0,0,0],[1,0,0,0]]];
    PERS wobjdata bfTurn:=[FALSE,TRUE,"",[[900,0,650],[1,0,0,0]],[[0,0,0],[1,0,0,0]]];
    PERS wobjdata bfCopy1:=[FALSE,TRUE,"",[[900,0,650],[1,0,0,0]],[[0,0,0],[1,0,0,0]]];
    PERS wobjdata bfCopy2:=[FALSE,TRUE,"",[[900,0,650],[1,0,0,0]],[[0,0,0],[1,0,0,0]]];
    CONST robtarget bfP:=[[40,30,80],[0,0,1,0],[0,0,0,0],[9E9,9E9,9E9,9E9,9E9,9E9]];
    VAR robtarget bfS1;
    VAR robtarget bfS2;
    VAR robtarget bfS3;
    VAR robtarget bfS4;
    VAR num bfDone:=0;

    PROC BfConv()
        bfDone:=0;
        BfTurn 1,30;
        MoveL bfP,v500,fine,tool0\WObj:=bfCopy1;
        bfS1:=CRobT(\Tool:=tool0\WObj:=wobj0);
        MoveL bfP,v500,fine,tool0\WObj:=bfCopy2;
        bfS2:=CRobT(\Tool:=tool0\WObj:=wobj0);
        BfTurn 2,135;
        MoveL bfP,v500,fine,tool0\WObj:=bfCopy1;
        bfS3:=CRobT(\Tool:=tool0\WObj:=wobj0);
        MoveL bfP,v500,fine,tool0\WObj:=bfCopy2;
        bfS4:=CRobT(\Tool:=tool0\WObj:=wobj0);
        bfDone:=1;
    ENDPROC

    PROC BfTurn(num nSide,num nAngle)
        VAR pose pBase;
        VAR pose pTurn;
        IF nSide=1 THEN
            pBase:=bfSideA.uframe;
            bfTurn.ufmec:="ROB_1";
        ELSEIF nSide=2 THEN
            pBase:=bfSideB.uframe;
            bfTurn.ufmec:="ROB_1";
        ELSE
            Stop;
            EXIT;
        ENDIF
        pTurn.rot:=OrientZYX(nAngle,10,5);
        bfTurn.uframe:=PoseMult(pBase,pTurn);
        bfCopy1.uframe:=bfTurn.uframe;
        bfCopy2.uframe:=bfTurn.uframe;
    ENDPROC
ENDMODULE
