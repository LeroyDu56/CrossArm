MODULE LogicAndIo
    !=============================================================
    ! Synthetic demo cell: stack 12 parts with a suction cup.
    ! Exercises logic, loops, waits and I/O conversions.
    ! Written from scratch for the test suite.
    !=============================================================

    PERS tooldata tSuction:=[TRUE,[[0,0,120],[1,0,0,0]],[1.5,[0,0,60],[1,0,0,0],0,0,0]];
    PERS wobjdata wobjStack:=[FALSE,TRUE,"",[[800,-200,0],[1,0,0,0]],[[0,0,0],[1,0,0,0]]];

    CONST robtarget pStack:=[[500,-300,400],[0,0.707107,0.707107,0],[0,0,0,0],[9E9,9E9,9E9,9E9,9E9,9E9]];
    CONST jointtarget jSafe:=[[0,-20,20,0,70,0],[9E9,9E9,9E9,9E9,9E9,9E9]];

    PERS num nLayer:=0;
    PERS num nParts:=0;
    PERS num tSettle:=0.4;
    VAR num nRow:=0;
    VAR num nCol:=0;
    CONST num NB_COLS:=4;
    CONST num NB_PARTS:=12;
    VAR bool bStackFull:=FALSE;

    PROC Palletize()
        MoveAbsJ jSafe\NoEOffs,v1000,fine,tool0;
        WaitDI diStackReady,1;
        WHILE nParts<NB_PARTS AND NOT bStackFull DO
            nRow:=nParts DIV NB_COLS;
            nCol:=nParts MOD NB_COLS;
            IF nCol=0 OR diForceRow=1 THEN
                Set doRowStart;
            ELSE
                Reset doRowStart;
            ENDIF
            MoveJ Offs(pStack,0,0,150),v800,z50,tSuction\WObj:=wobjStack;
            MoveL pStack,v200,fine,tSuction\WObj:=wobjStack;
            SetDO doVacuum,1;
            WaitDO doVacuum,1;
            WaitTime tSettle;
            MoveL Offs(pStack,0,0,150),v500,z20,tSuction\WObj:=wobjStack;
            nParts:=nParts+1;
            IF nParts>=NB_PARTS bStackFull:=TRUE;
        ENDWHILE
        Stop;
    ENDPROC

    PROC CountDown()
        FOR k FROM 3 TO 1 STEP -1 DO
            nLayer:=k;
            WaitTime 0.5;
        ENDFOR
        WaitUntil diStackReady=0 OR nLayer<>0;
        IF diAbort=1 THEN
            EXIT;
        ENDIF
        IF nLayer>2 RETURN;
        WaitTime 1.5;
    ENDPROC
ENDMODULE
