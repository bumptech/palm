/* TODO --
 *
 * scan for security..
 *
 */
#include <stdio.h>
#include <stdlib.h>
#include <stdint.h>
#include <assert.h>
#include <string.h>

#include "palmcore.h"

void write_varint_value(unsigned char **ptr, uint64_t value) {
    unsigned char *chr = (unsigned char *)*ptr;
    while (1) {
        *chr = (value & 127);
        value = value >> 7;
        if (!value)
            break;
        *chr |= 128;
        chr++;
    }
    *ptr = chr + 1;
}

int read_varint_value(unsigned char **ptr, uint64_t *result, int *iters,
        unsigned char *limit) {
    unsigned char *chr = (unsigned char*)*ptr;
    uint64_t acc = 0;
    uint64_t x;
    for (x=0; x < 10; x++) {
        acc |= ((uint64_t)(*chr & 127)) << (7 * x);
        if (!(*chr & 128))
            break;
        chr++;
        if (chr == limit) return 0; // overflow
    }
    if (x == 10)
        return 0; // error reading varint.. too long!
    chr++;

    *ptr = (char *)chr;

    *result = acc;
    *iters = x;
    return 1;
}

static int pbf_ensure_space(pbf_protobuf *pbf, int max) {
    if (max > 100000)
        return 0; // refuse to allocate this much ram

    int mark = pbf->num_marks;
    pbf->num_marks = max + 100;
    pbf->marks = realloc(pbf->marks, sizeof(pbf_mark) * pbf->num_marks);

    for (; mark < pbf->num_marks; mark++)
        pbf->marks[mark].exists = 0;

    return 1;
}

int pbf_exists(pbf_protobuf *pbf, uint64_t field_num) {
    if (field_num < 0 || field_num > pbf->num_marks) // soon, max mark
        return 0;
    return pbf->marks[field_num].exists;
}

static void pbf_scan (pbf_protobuf *pbf) {
    uint64_t key;
    int success, iters;
    uint64_t field_num;
    uint64_t field_type;
    unsigned char *ptr = pbf->data;
    pbf->parsed = 0;
    unsigned char *limit = pbf->data + pbf->data_length;
    while (ptr < limit) {
        char *start = ptr;
        success = read_varint_value(&ptr, &key, &iters, limit);
        if (!success) return;

        field_num = key >> 3;
        field_type = key & 7;

        if (field_num >= pbf->num_marks)
            pbf_ensure_space(pbf, field_num);
        if (field_num > pbf->max_mark)
            pbf->max_mark = field_num;

        pbf_mark *cur = &pbf->marks[field_num];
        cur->exists = 1;
        cur->ftype = field_type;
        cur->raw = start;
        cur->buf_len = 0;
        switch (field_type) {
            case pbf_type_varint:
                if (!read_varint_value(&ptr, &cur->fdata.i64, &iters, limit)) return;
                break;
            case pbf_type_length:
                if (!read_varint_value(&ptr, &cur->fdata.s.len, &iters, limit)) return;
                cur->fdata.s.data = ptr;
                ptr += cur->fdata.s.len;
                break;
            case pbf_type_fixed64:
                if (limit - ptr < 8) return;
                cur->fdata.i64 = *ptr;
                ptr += sizeof(uint64_t);
                break;
            case pbf_type_fixed32:
                if (limit - ptr < 4) return;
                cur->fdata.i32 = *ptr;
                ptr += sizeof(uint32_t);
                break;
            default: // unknown type
                return;
        }
        if (ptr > limit)
            return; // overflow on string length, etc
        cur->raw_len = ptr - cur->raw;
    }
    pbf->parsed = 1;
}

unsigned char *pbf_serialize(pbf_protobuf *pbf, int *length) {
    register int x;

    uint32_t size = 0;
    pbf_mark *mark;
    /* XXX protect against giant allocations? */

    /* maximum size needed? */
    uint32_t *fields = malloc(pbf->max_mark * sizeof(uint32_t));
    uint32_t *cf = fields;
    for(x=1; x <= pbf->max_mark; x++) {
        mark = &pbf->marks[x];
        if (mark->exists) {
            size += mark->raw_len + mark->buf_len;
            *cf = x;
            cf++;
        }
    }
    *cf = 0;

    unsigned char *out = (char *)malloc(size);

    unsigned char *ptr = out;

    for(cf=fields; *cf != 0; cf++) {
        mark = &pbf->marks[*cf];
        if (mark->exists) {
            if (mark->buf_len) {
                memcpy(ptr, mark->buf, mark->buf_len);
                ptr += mark->buf_len;
            }
            if (mark->raw_len) {
                memcpy(ptr, mark->raw, mark->raw_len);
                ptr += mark->raw_len;
            }
        }
    }

    *length = ptr - out;
    free(fields);
    return out;
}

pbf_protobuf * pbf_load(char *data, uint64_t size) {
    pbf_protobuf *pbf = (pbf_protobuf *)malloc(sizeof(pbf_protobuf));

    pbf->data = (unsigned char *)data; // assumed.. retention on behalf of caller
    pbf->data_length = size; // assumed.. retention on behalf of caller
    pbf->num_marks = 0;
    pbf->max_mark = 0;
    pbf->marks = NULL;

    pbf_scan(pbf);

    if (!pbf->parsed) {
        pbf_free(pbf);
        return NULL;
    }

    return pbf;
}

void pbf_free(pbf_protobuf *pbf) {
    if (pbf->marks)
        free(pbf->marks);
    free(pbf);
}

int pbf_get_bytes(pbf_protobuf *pbf, uint64_t field_num,
        char **out, uint64_t *length) {
    if (field_num < 0 || field_num >= pbf->num_marks)
        return 0;
    pbf_mark *cur = &pbf->marks[field_num];
    if (!cur->exists)
        return 0;

    *out = cur->fdata.s.data;
    *length = cur->fdata.s.len;

    return 1;
}

int pbf_set_bytes(pbf_protobuf *pbf, uint64_t field_num,
        char *out, uint64_t length) {
    if (field_num >= pbf->num_marks)
        pbf_ensure_space(pbf, field_num);
    if (field_num > pbf->max_mark)
        pbf->max_mark = field_num;
    pbf_mark *cur = &pbf->marks[field_num];

    cur->exists = 1;

    cur->fdata.s.data = cur->raw = out;
    cur->fdata.s.len = cur->raw_len = length;
    unsigned char *ptr = cur->buf;
    write_varint_value(&ptr, field_num << 3 | pbf_type_length);
    write_varint_value(&ptr, length);
    cur->buf_len = ptr - cur->buf;

    return 1;
}

int pbf_set_integer(pbf_protobuf *pbf, uint64_t field_num,
        uint64_t value, int fixed) {
    if (field_num >= pbf->num_marks)
        pbf_ensure_space(pbf, field_num);
    if (field_num > pbf->max_mark)
        pbf->max_mark = field_num;
    pbf_mark *cur = &pbf->marks[field_num];

    cur->exists = 1;
    cur->raw_len = 0;
    cur->fdata.i64 = value;

    unsigned char *ptr = cur->buf;
    if (!fixed) {
        write_varint_value(&ptr, field_num << 3 | pbf_type_varint);
        write_varint_value(&ptr, value);
    }
    else if (fixed == 32){
        write_varint_value(&ptr, field_num << 3 | pbf_type_fixed32);
        *((uint32_t *)ptr) = (uint32_t)value;
        ptr += 4;
    }
    else if (fixed == 64){
        write_varint_value(&ptr, field_num << 3 | pbf_type_fixed64);
        *((uint64_t *)ptr) = (uint64_t)value;
        ptr += 8;
    }
    else
        assert(0); // bad internal API call

    cur->buf_len = ptr - cur->buf;

    return 1;
}

int pbf_set_signed_integer(pbf_protobuf *pbf, uint64_t field_num,
        int64_t value, int zigzag) {
    if (field_num >= pbf->num_marks)
        pbf_ensure_space(pbf, field_num);
    if (field_num > pbf->max_mark)
        pbf->max_mark = field_num;
    pbf_mark *cur = &pbf->marks[field_num];

    cur->exists = 1;
    cur->raw_len = 0;

    unsigned char *ptr = cur->buf;

    write_varint_value(&ptr, field_num << 3 | pbf_type_varint);
    if (!zigzag) {
        cur->fdata.i64 = (uint64_t)value;
        write_varint_value(&ptr, (uint64_t)value);
    }
    else {
        uint64_t encoded = (value << 1) ^ (value >> 63);
        cur->fdata.i64 = encoded;
        write_varint_value(&ptr, encoded);
    }

    cur->buf_len = ptr - cur->buf;

    return 1;
}

int pbf_get_integer(pbf_protobuf *pbf, uint64_t field_num, uint64_t *res) {
    if (field_num < 0 || field_num >= pbf->num_marks)
        return 0;
    pbf_mark *cur = &pbf->marks[field_num];
    if (!cur->exists)
        return 0;
    switch (cur->ftype) {
        case pbf_type_fixed32:
            *res = cur->fdata.i32;
            break;
        default:
            *res = cur->fdata.i64;
            break;
    }

    return 1;
}

int pbf_get_signed_integer(pbf_protobuf *pbf,
        uint64_t field_num, int64_t *res,
        int32_t *res32, int use_zigzag) {
    if (field_num < 0 || field_num >= pbf->num_marks)
        return 0;
    pbf_mark *cur = &pbf->marks[field_num];
    if (!cur->exists)
        return 0;

    int is_32 = res32 != NULL ? 1 : 0;
    switch (cur->ftype) {
        case pbf_type_fixed32:
            assert(is_32);
            assert(!use_zigzag);
            *res32 = cur->fdata.i32;
            break;
        default:
            if (!use_zigzag) {
                if (is_32) {
                    *res32 = (int32_t)cur->fdata.i64;
                }
                else
                    *res = cur->fdata.i64;
            }
            else {
                int64_t t = !(cur->fdata.i64 & 0x1) ? 
                            cur->fdata.i64 >> 1 : 
                            (cur->fdata.i64 >> 1) ^ (~0);

                if (is_32) 
                    *res32 = t;
                else 
                    *res = t;
            }
            break;
    }

    return 1;
}

/*
int main(int argc, char ** argv) {

    char inp[500000];
    int bread = read(0, &inp, 500000);

    pbf_protobuf *pbf = pbf_load(inp, bread);

    char *optr;
    char buf[50];
    uint64_t length;

    pbf_get_bytes(pbf, 1, &optr, &length);
    strncpy(buf, optr, length);
    buf[length] = 0;
    printf("1: %s\n", buf);

    int32_t si;
    uint32_t ui;
    int64_t sl;
    uint64_t ul;

    // unsigned 32
    pbf_get_integer(pbf, 2, &ul);
    ui = ul;
    printf("2: %u\n", ui);

    // signed 32, not zigzag
    pbf_get_signed_integer(pbf, 3, NULL, &si, 0);
    printf("3: %d\n", si);

    // signed 32, zigzag
    pbf_get_signed_integer(pbf, 4, NULL, &si, 1);
    printf("4: %d\n", si);

    // unsigned 64
    pbf_get_integer(pbf, 5, &ul);
    printf("5: %llu\n", ul);

    // signed 64, not zigzag
    pbf_get_signed_integer(pbf, 6, &sl, NULL, 0);
    printf("6: %lld\n", sl);

    // signed 64, zigzag
    pbf_get_signed_integer(pbf, 7, &sl, NULL, 1);
    printf("7: %lld\n", sl);

    pbf_free(pbf);
    return 0;
}
*/
