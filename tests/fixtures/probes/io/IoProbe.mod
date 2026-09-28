MODULE IoProbe
    ! CrossArm - I/O probe: see tools/make_io_probe.py.
    VAR num nInvert:=0;
    VAR num nPulse:=0;
    VAR num nTime:=0;
    VAR clock ckProbe;

    PROC IoProbe()
        nInvert:=0;
        nPulse:=0;
        nTime:=0;
        Reset doProbeA;
        InvertDO doProbeA;
        IF DOutput(doProbeA)=1 nInvert:=nInvert+1;
        InvertDO doProbeA;
        IF DOutput(doProbeA)=0 nInvert:=nInvert+10;
        Reset doProbeB;
        PulseDO\PLength:=0.5,doProbeB;
        WaitTime 0.1;
        IF DOutput(doProbeB)=1 nPulse:=nPulse+1;
        WaitTime 0.6;
        IF DOutput(doProbeB)=0 nPulse:=nPulse+10;
        ClkReset ckProbe;
        ClkStart ckProbe;
        WaitTime 0.5;
        ClkStop ckProbe;
        nTime:=ClkRead(ckProbe);
        SetAO aoProbe,2.5;
    ENDPROC
ENDMODULE
