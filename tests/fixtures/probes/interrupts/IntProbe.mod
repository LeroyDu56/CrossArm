MODULE IntProbe
    ! CrossArm - interrupt probe: see tools/make_interrupt_probe.py.
    VAR intnum iEdge;
    VAR intnum iOnce;
    VAR intnum iFall;
    VAR intnum iWatch;
    PERS num nState:=0;
    VAR num nHits:=0;
    VAR num nOnce:=0;
    VAR num nFall:=0;
    VAR num nWatch:=0;
    VAR num nLast:=0;

    PROC IntProbe()
        nHits:=0;
        nOnce:=0;
        nFall:=0;
        nWatch:=0;
        nLast:=0;
        nState:=0;
        Reset doProbeA;
        Reset doProbeB;
        IDelete iEdge;
        IDelete iOnce;
        IDelete iFall;
        IDelete iWatch;
        CONNECT iEdge WITH tEdge;
        ISignalDO doProbeA,1,iEdge;
        CONNECT iOnce WITH tOnce;
        ISignalDO\Single,doProbeB,1,iOnce;
        CONNECT iFall WITH tFall;
        ISignalDO doProbeB,0,iFall;
        CONNECT iWatch WITH tWatch;
        IPers nState,iWatch;
        WaitTime 0.1;
        FOR i FROM 1 TO 3 DO
            SetDO doProbeA,1;
            WaitTime 0.1;
            SetDO doProbeA,0;
            WaitTime 0.1;
        ENDFOR
        SetDO doProbeB,1;
        WaitTime 0.1;
        SetDO doProbeB,0;
        WaitTime 0.1;
        SetDO doProbeB,1;
        WaitTime 0.1;
        SetDO doProbeB,0;
        WaitTime 0.1;
        nState:=5;
        WaitTime 0.1;
        nState:=7;
        WaitTime 0.1;
        ISleep iEdge;
        IntPulse;
        IWatch iEdge;
        WaitTime 0.1;
        IntPulse;
        IDelete iEdge;
        IDelete iFall;
        IDelete iWatch;
        IntPulse;
        nState:=9;
        WaitTime 0.1;
    ENDPROC

    PROC IntPulse()
        SetDO doProbeA,1;
        WaitTime 0.1;
        SetDO doProbeA,0;
        WaitTime 0.1;
    ENDPROC

    PROC IntAdd()
        nHits:=nHits+1;
    ENDPROC

    TRAP tEdge
        IntAdd;
    ENDTRAP

    TRAP tOnce
        nOnce:=nOnce+1;
    ENDTRAP

    TRAP tFall
        nFall:=nFall+1;
    ENDTRAP

    TRAP tWatch
        nWatch:=nWatch+1;
        nLast:=nState;
    ENDTRAP
ENDMODULE
