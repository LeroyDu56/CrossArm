MODULE HmiAndGroups
    !=============================================================
    ! Synthetic demo: operator messages and group I/O.
    ! Written from scratch for the test suite.
    !=============================================================
    CONST string MSG_READY:="Cell ready";
    VAR num nCode:=0;

    PROC ReportCycle()
        TPErase;
        TPWrite MSG_READY;
        TPWrite "Waiting for [code]";
        nCode:=GInput(giCycleCode);
        SetGO goEchoCode,nCode;
        SetGO goStatus,3;
        TPWrite "Exactly 24 characters ok";
        TPWrite "Cycle "+"started";
    ENDPROC
ENDMODULE
