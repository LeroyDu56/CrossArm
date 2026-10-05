MODULE ArrayWriteProbe
    ! CrossArm - probe of arrays the programs write: see tools/make_array_write_probe.py.
    VAR num awGrid{3,4};
    PERS num awTable{5}:=[10,20,30,40,50];
    VAR num awK:=0;
    VAR num awSum:=0;
    VAR num awCheck:=0;
    VAR num awFixed:=0;
    VAR num awCorners:=0;
    VAR num awSecond:=0;

    PROC AwFill()
        FOR i FROM 1 TO 3 DO
            FOR j FROM 1 TO 4 DO
                awGrid{i,j}:=i*10+j;
            ENDFOR
        ENDFOR
    ENDPROC

    PROC AwAdd()
        FOR i FROM 1 TO 3 DO
            FOR j FROM 1 TO 4 DO
                awSum:=awSum+awGrid{i,j};
            ENDFOR
        ENDFOR
    ENDPROC

    PROC AwProbe()
        awSum:=0;
        awCheck:=0;
        awFixed:=0;
        awCorners:=0;
        awSecond:=0;
        awTable{1}:=10;
        awTable{2}:=20;
        awTable{3}:=30;
        awTable{4}:=40;
        awTable{5}:=50;
        AwFill;
        AwAdd;
        awTable{2}:=awTable{2}+awTable{5};
        Incr awTable{3};
        awK:=4;
        awTable{awK+1}:=awTable{awK}*2;
        awCheck:=awTable{1}+awTable{2}+awTable{3}+awTable{4}+awTable{5};
        awFixed:=awGrid{2,3};
        awCorners:=awGrid{3,4}+awGrid{1,1};
        awK:=2;
        awSecond:=awGrid{awK,awK+2}+awTable{awK};
    ENDPROC

    PROC Probe()
        VAR iodev file;
        VAR num v;
        AwProbe;
        Open "HOME:" \File:="arraywriteprobe.txt", file \Write;
        v:=awSum;
        Write file, "awSum " \Num:=v;
        v:=awCheck;
        Write file, "awCheck " \Num:=v;
        v:=awFixed;
        Write file, "awFixed " \Num:=v;
        v:=awCorners;
        Write file, "awCorners " \Num:=v;
        v:=awSecond;
        Write file, "awSecond " \Num:=v;
        Close file;
    ENDPROC
ENDMODULE
