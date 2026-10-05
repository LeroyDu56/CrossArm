MODULE FlagProbe
    ! CrossArm - flag probe: see tools/make_flag_probe.py.
    VAR bool fpBig;
    VAR bool fpBoth;
    VAR bool fpNot;
    VAR bool fpCopy;
    VAR bool fpText;
    VAR bool fpGo;
    VAR string fpState;
    VAR num fpA:=0;
    VAR num fpB:=0;
    VAR num fpN1:=0;
    VAR num fpN2:=0;
    VAR num fpN3:=0;
    VAR num fpN4:=0;
    VAR num fpN5:=0;
    VAR num fpTurns:=0;

    PROC FpProbe()
        fpN1:=0;
        fpN2:=0;
        fpN3:=0;
        fpN4:=0;
        fpN5:=0;
        fpTurns:=0;
        fpA:=3;
        fpB:=7;
        fpState:="RUN";
        fpBig:=fpA<5;
        fpBoth:=fpA<5 AND fpB>8;
        fpNot:=NOT fpBig;
        fpCopy:=fpBig;
        fpText:=fpState="RUN" AND fpA=3;
        IF fpBig fpN1:=1;
        IF fpBoth fpN2:=1;
        IF fpNot fpN3:=1;
        IF fpCopy fpN4:=1;
        IF fpText fpN5:=1;
        fpGo:=TRUE;
        WHILE fpGo DO
            Incr fpTurns;
            fpGo:=fpTurns<4;
        ENDWHILE
    ENDPROC

    PROC Probe()
        VAR iodev file;
        VAR num v;
        FpProbe;
        Open "HOME:" \File:="flagprobe.txt", file \Write;
        v:=fpN1;
        Write file, "fpN1 " \Num:=v;
        v:=fpN2;
        Write file, "fpN2 " \Num:=v;
        v:=fpN3;
        Write file, "fpN3 " \Num:=v;
        v:=fpN4;
        Write file, "fpN4 " \Num:=v;
        v:=fpN5;
        Write file, "fpN5 " \Num:=v;
        v:=fpTurns;
        Write file, "fpTurns " \Num:=v;
        Close file;
    ENDPROC
ENDMODULE
