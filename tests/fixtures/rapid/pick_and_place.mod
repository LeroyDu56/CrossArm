MODULE PickAndPlace
    !=============================================================
    ! Synthetic demo cell: pick parts from a conveyor, place them
    ! on a 3-slot fixture. Written from scratch for the test suite.
    !=============================================================

    ! ---- Tools and work objects ----
    PERS tooldata tGripper:=[TRUE,[[0,0,185.5],[1,0,0,0]],[2.4,[0,0,90],[1,0,0,0],0,0,0]];
    TASK PERS wobjdata wobjFixture:=[FALSE,TRUE,"",[[1250,-400,720],[0.707107,0,0,0.707107]],[[0,0,0],[1,0,0,0]]];

    ! ---- Positions ----
    CONST robtarget pHome:=[[600,0,900],[0,0,1,0],[0,0,0,0],[9E+09,9E+09,9E+09,9E+09,9E+09,9E+09]];
    CONST robtarget pPick:=[[812.35,-245.1,305],[0.004363,-0.707094,0.707094,-0.004363],[-1,0,-1,0],[9E+09,9E+09,9E+09,9E+09,9E+09,9E+09]];  ! conveyor end
    CONST robtarget pArcMid:=[[900,0,500],[0,0,1,0],[0,0,0,0],[9E9,9E9,9E9,9E9,9E9,9E9]];
    CONST robtarget pArcEnd:=[[950,100,450],[0,0,1,0],[0,0,0,0],[9E9,9E9,9E9,9E9,9E9,9E9]];
    CONST jointtarget jParking:=[[0,-30,30,0,90,0],[9E+09,9E+09,9E+09,9E+09,9E+09,9E+09]];
    VAR robtarget pPlace;

    ! ---- Counters ----
    VAR num nSlot:=0;
    PERS num nCycles:=0;
    CONST num NB_SLOTS:=3;
    VAR num nOffsets{3}:=[0,120,240];
    LOCAL VAR bool bPartPresent:=FALSE;

    RECORD partdata
        num id;
        string label;
    ENDRECORD

    PROC main()
        MoveAbsJ jParking\NoEOffs,v1000,fine,tool0;
        MoveJ pHome,v1000,z50,tGripper;
        WHILE TRUE DO
            IF DI_PartReady=1 Pick;
            FOR i FROM 1 TO NB_SLOTS DO
                nSlot:=i;
                Place;
            ENDFOR
            nCycles:=nCycles+1;
        ENDWHILE
    ENDPROC

    PROC Pick()
        ! approach, grip, retract
        MoveJ Offs(pPick,0,0,100),v1000,z20,tGripper;
        MoveL pPick,v200,fine,tGripper;
        Set DO_GripperClose;
        WaitTime 0.3;
        MoveL Offs(pPick,0,0,100),v500,z10,tGripper;
    ENDPROC

    PROC Place()
        pPlace:=Offs(pHome,nOffsets{nSlot},0,-400);
        pPlace.trans.z:=pPlace.trans.z+2.5;
        IF nSlot=1 THEN
            MoveJ pPlace,v800,z20,tGripper\WObj:=wobjFixture;
        ELSEIF nSlot=2 THEN
            MoveC pArcMid,pArcEnd,v300,z10,tGripper\WObj:=wobjFixture;
        ELSE
            MoveL pPlace,v300,fine,tGripper\WObj:=wobjFixture;
        ENDIF
        Reset DO_GripperClose;
        WaitTime\InPos,0.2;
        GOTO skip_log;
        TPWrite "Placed in slot "\Num:=nSlot;
        skip_log:
    ERROR
        IF ERRNO=ERR_WAIT_MAXTIME RETRY;
        RAISE;
    ENDPROC

    FUNC bool IsFixtureFull()
        RETURN nSlot>=NB_SLOTS AND NOT bPartPresent;
    ENDFUNC
ENDMODULE
