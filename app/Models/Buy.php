<?php

namespace App\Models;

use Illuminate\Database\Eloquent\Factories\HasFactory;
use Illuminate\Database\Eloquent\Model;
use Illuminate\Database\Eloquent\Relations\BelongsTo;

class Buy extends Model
{
    use HasFactory;

    protected $table = 'buy';

    public function reserve(): BelongsTo
    {
        return $this->belongsTo(Reservation::class);
    }
    public function passenger(): BelongsTo
    {
        return $this->belongsTo(Passenger::class);
    }
}
