MODULE KarelFileProbe
    ! CrossArm - KAREL file probe: see tools/make_karel_file_probe.py.
    VAR iodev kfLog;
    VAR iodev kfMany{2};
    VAR num kfDone:=0;
    VAR num kfI:=0;
    VAR num kfV:=0;

    PROC KfProbe()
        kfDone:=0;
        Open "HOME:" \File:="kfprobe.txt", kfLog \Write;
        Write kfLog, "CrossArm file probe";
        Write kfLog, "it's a,b;c (x)";
        Write kfLog, "0123456789012345678901234567890123456789012345678901234567890123456789";
        kfV:=1/3;
        Write kfLog, "n0 " \Num:=kfV;
        kfV:=2.5;
        Write kfLog, "n1 " \Num:=kfV;
        kfV:=123456.7;
        Write kfLog, "n2 " \Num:=kfV;
        kfV:=1234567;
        Write kfLog, "n3 " \Num:=kfV;
        kfV:=-0.000012;
        Write kfLog, "n4 " \Num:=kfV;
        kfV:=-7;
        Write kfLog, "n5 " \Num:=kfV;
        kfV:=0.1+0.2;
        Write kfLog, "n6 " \Num:=kfV;
        kfV:=99.99999;
        Write kfLog, "n7 " \Num:=kfV;
        kfV:=0.0123456;
        Write kfLog, "n8 " \Num:=kfV;
        kfV:=12.345678;
        Write kfLog, "n9 " \Num:=kfV;
        kfV:=3.14159265;
        Write kfLog, "n10 " \Num:=kfV;
        kfV:=-0.3;
        Write kfLog, "n11 " \Num:=kfV;
        kfV:=0.000004;
        Write kfLog, "n12 " \Num:=kfV;
        kfV:=0;
        Write kfLog, "n13 " \Num:=kfV;
        kfV:=100;
        Write kfLog, "n14 " \Num:=kfV;
        Write kfLog, "no line, " \NoNewLine;
        Write kfLog, "end";
        Close kfLog;
        Open "HOME:" \File:="kfprobe.txt", kfLog \Append;
        KfLine "appended", 3;
        Close kfLog;
        kfI:=2;
        Open diskhome \File:="kfsecond.txt", kfMany{kfI} \Write;
        Write kfMany{kfI}, "second";
        Close kfMany{kfI};
        Open "HOME:/kfsecond.txt", kfMany{1} \Append;
        Write kfMany{1}, "added";
        Close kfMany{1};
        Open "HOME:" \File:="kfthird.txt", kfLog \Write;
        Write kfLog, "first";
        Close kfLog;
        Open "HOME:" \File:="kfthird.txt", kfLog;
        Write kfLog, "rewritten";
        Close kfLog;
        kfDone:=1;
    ENDPROC

    PROC KfLine(string text, num n)
        Write kfLog, "[" + text + "] " \Num:=n;
    ENDPROC
ENDMODULE
