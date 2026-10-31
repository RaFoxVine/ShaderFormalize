struct Packet { uint word; float value; };

Packet SelectPacket(float4 input) {
    uint word = asuint(input.x);
    Packet selected;
    if (word < 0x80000000u) {
        selected.word = word & 0x00FFFFFFu;
        selected.value = input.y;
    } else {
        selected.word = word ^ 0x85EBCA6Bu;
        if (input.w != input.w) { selected.value = input.w; }
        else { selected.value = input.z; }
    }
    Packet copied = selected;
    copied.word ^= 0x01010101u;
    return copied;
}

float4 main(float4 input : COLOR0) : SV_Target {
    Packet selected = SelectPacket(input);
    return float4(asfloat(selected.word), selected.value, input.z, input.w);
}
