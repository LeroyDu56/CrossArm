MODULE FlagArrayProbe
    ! CrossArm - probe of arrays of bools: see tools/make_flag_array_probe.py.
    VAR bool faSlot{6};
    PERS bool faDone{2,3}:=[[FALSE,FALSE,FALSE],[FALSE,FALSE,FALSE]];
    VAR num faK:=0;
    VAR num faCount:=0;
    VAR num faPairs:=0;
    VAR num faFixed:=0;
    VAR num faFirst:=0;

    PROC FaMark()
        FOR i FROM 1 TO 6 DO
            faSlot{i}:=i>3;
        ENDFOR
    ENDPROC

    PROC FaTally()
        FOR i FROM 1 TO 6 DO
            IF faSlot{i} faCount:=faCount+1;
        ENDFOR
    ENDPROC

    PROC FaProbe()
        faCount:=0;
        faPairs:=0;
        faFixed:=0;
        faFirst:=0;
        FOR i FROM 1 TO 2 DO
            FOR j FROM 1 TO 3 DO
                faDone{i,j}:=FALSE;
            ENDFOR
        ENDFOR
        FaMark;
        faSlot{1}:=TRUE;
        faSlot{2}:=faSlot{5} AND (NOT faSlot{3});
        FaTally;
        faK:=2;
        faDone{faK,faK+1}:=TRUE;
        faDone{1,faK}:=faSlot{faK+1};
        faDone{1,1}:=NOT faDone{2,3};
        faDone{2,1}:=faSlot{faK*3};
        FOR i FROM 1 TO 2 DO
            FOR j FROM 1 TO 3 DO
                IF faDone{i,j} faPairs:=faPairs+i*10+j;
            ENDFOR
        ENDFOR
        IF faSlot{2} AND faDone{2,3} faFixed:=1;
        IF NOT faSlot{3} faFirst:=1;
    ENDPROC

    PROC Probe()
        VAR iodev file;
        VAR num v;
        FaProbe;
        Open "HOME:" \File:="flagarrayprobe.txt", file \Write;
        v:=faCount;
        Write file, "faCount " \Num:=v;
        v:=faPairs;
        Write file, "faPairs " \Num:=v;
        v:=faFixed;
        Write file, "faFixed " \Num:=v;
        v:=faFirst;
        Write file, "faFirst " \Num:=v;
        Close file;
    ENDPROC
ENDMODULE
