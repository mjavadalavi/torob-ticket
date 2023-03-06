<?php

namespace App\Http\Controllers\API;

use App\Classes\Encoding;
use App\Enums\BusType;
use App\Enums\ReservationStatus;
use App\Enums\Status;
use App\Enums\StatusCode;
use App\Http\Controllers\Controller;
use App\Http\Requests\CancelReserveRequest;
use App\Http\Requests\StoreReserveRequest;
use App\Models\Chairs;
use App\Models\Reservation;
use App\Models\WeeklySchedule;
use Illuminate\Http\JsonResponse;
use Symfony\Component\HttpFoundation\Response;

class ReserveController extends Controller
{
    /**
     * @OA\Post(
     *      path="/reserve",
     *      operationId="storeReserveRequest",
     *      tags={"reserve"},
     *      summary="Store new Reserve",
     *      description="Returns json of result storing data",
     *      @OA\RequestBody(
     *         @OA\MediaType(
     *             mediaType="application/json",
     *             @OA\Schema(
     *                 example={
     *                      "search_hash":"s3w3rf",
     *                      "passenger_count":"5",
     *                      "chairs":"['0'=>1,'1'=>2,'2'=>3,'3'=>4]",
     *                 }
     *             )
     *         )
     *      ),
     *      @OA\Parameter(
     *           description="a hash id of searched by user",
     *           in="path",
     *           name="search_hash",
     *           required=true,
     *           @OA\Schema(type="string"),
     *       ),
     *      @OA\Parameter(
     *           description="count of passengers",
     *           in="path",
     *           name="passenger_count",
     *           required=true,
     *           @OA\Schema(type="string"),
     *
     *       ),
     *      @OA\Parameter(
     *           description="an array of chairs user needed.",
     *           in="path",
     *           name="chairs",
     *           required=true,
     *           @OA\Schema(type="string"),
     *           @OA\Items(
     *               type="array",
     *               @OA\Items()
     *           ),
     *       ),
     *      @OA\Response(
     *          response=201,
     *          description="Successful operation",
     *          content={
     *             @OA\MediaType(
     *                 mediaType="application/json",
     *                 @OA\Schema(
     *                     example={
     *                          "id":1,
     *                          "weekly_schedule_id":3,
     *                          "chair_id": 2,
     *                          "passenger_count": 20,
     *                          "chairs": "[1,2,3,4]",
     *                          "status":1
     *                     }
     *                 )
     *             )
     *         }
     *       ),
     *      @OA\Response(
     *          response=404,
     *          description="Not Found",
     *          content={
     *             @OA\MediaType(
     *                 mediaType="application/json",
     *                 @OA\Schema(
     *                     example={
     *                          "status":"Failed",
     *                          "code":"-1",
     *                          "data":"ticket with this id not found"
     *                     }
     *                 )
     *             )
     *         }
     *      ),
     *      @OA\Response(
     *          response=400,
     *          description="Bad Request",
     *          content={
     *             @OA\MediaType(
     *                 mediaType="application/json",
     *                 @OA\Schema(
     *                     example={
     *                          "status":"HTTP Bad Request",
     *                          "code":"400",
     *                          "data":"your request don't have some parameter."
     *                     }
     *                 )
     *             )
     *         }
     *      )
     * )
     */

    public function store(StoreReserveRequest $request): JsonResponse
    {
        if ($request->validated()){
            $search_id = explode('|',Encoding::base64url_decode($request->input("search_hash")));
            $passenger_count = $request->input("passenger_count");
            $user_chairs = array_map('intval', $request->input("chairs"));
            $week =  WeeklySchedule::find($search_id)->first();
            $db_chair = Chairs::find($search_id[1])->first();
            if ($week && $db_chair){
                $reserve = new Reservation();
                $reserve->weekly_schedule_id = $search_id[0];
                $reserve->bus_empty_chairs_id = $search_id[1];
                $reserve->passenger_count = $passenger_count;
                $reserve->user_chairs = array_values($user_chairs);
                $reserve->status = ReservationStatus::Pending;
                $reserve->save();

                // remove chairs from record
                $db_chair->user_chairs = array_diff($db_chair->user_chairs, $user_chairs);
                $db_chair->save();

                return response()->json(['status' => Status::Success , "code" => StatusCode::Success, "data"=> $reserve])
                    ->setStatusCode(Response::HTTP_ACCEPTED)
                    ->header('Content-Type', 'application/json');
            }else{
                return response()->json(['status' => Status::Failed , "code" => StatusCode::Failed, "data"=>"your hash code is not valid."])
                    ->setStatusCode(Response::HTTP_NOT_FOUND)
                    ->header('Content-Type', 'application/json');
            }

        }else{
            return response() ->json(['status' => Status::HTTP_BAD_REQUEST , "code" => StatusCode::Success, "data"=> "your request don't have some parameter."])
                ->setStatusCode(Response::HTTP_BAD_REQUEST)
                ->header('Content-Type', 'application/json');
        }
    }

    /**
     * @OA\Post(
     *      path="/cancellation",
     *      operationId="CancelReserveRequest",
     *      tags={"reserve"},
     *      summary="Cancel a Reserve",
     *      description="Returns json of result cancelling.",
     *      @OA\RequestBody(
     *         @OA\MediaType(
     *             mediaType="application/json",
     *             @OA\Schema(
     *                 example={
     *                      "reserve_id":5
     *                 }
     *             )
     *         )
     *      ),
     *      @OA\Parameter(
     *           description="an id of users reserved.",
     *           in="path",
     *           name="reserve_id",
     *           required=true,
     *           @OA\Schema(type="integer"),
     *       ),
     *      @OA\Response(
     *          response=201,
     *          description="Successful operation",
     *          content={
     *             @OA\MediaType(
     *                 mediaType="application/json",
     *                 @OA\Schema(
     *                     example={
     *                          "status":"Success",
     *                          "code":"1",
     *                          "data":"your reservations successfully cancelled"
     *                     }
     *                 )
     *             )
     *         }
     *       ),
     *      @OA\Response(
     *          response=404,
     *          description="Not Found",
     *          content={
     *             @OA\MediaType(
     *                 mediaType="application/json",
     *                 @OA\Schema(
     *                     example={
     *                          "status":"Failed",
     *                          "code":"-1",
     *                          "data":"ticket with this id not found"
     *                     }
     *                 )
     *             )
     *         }
     *      ),
     *      @OA\Response(
     *          response=400,
     *          description="Bad Request",
     *          content={
     *             @OA\MediaType(
     *                 mediaType="application/json",
     *                 @OA\Schema(
     *                     example={
     *                          "status":"HTTP Bad Request",
     *                          "code":"400",
     *                          "data": "your request don't have some parameter."
     *                     }
     *                 )
     *             )
     *         }
     *      )
     * )
     */
    public function cancellation(CancelReserveRequest $request):JsonResponse
    {
        if ($request->validated()){
            $reserve = Reservation::find($request->input("reserve_id"));
            if ($reserve){

                $reserve->status = ReservationStatus::Cancel;
                $reserve->save();

                $chair = Chairs::find($reserve->user_chairs)->first();
                $chair->user_chairs[] = $reserve->user_chairs;
                $chair->save();

                $response = ['status' => Status::Success , "code" => StatusCode::Success, "data"=> "your reservations successfully cancelled"];
                $response_code = Response::HTTP_OK;

            }else{
                $response = ['status' => Status::Failed , "code" => StatusCode::Failed, "data"=>"ticket with this id not found"];
                $response_code = Response::HTTP_NOT_FOUND;
            }
        }else{
            $response = ['status' => Status::HTTP_BAD_REQUEST , "code" => StatusCode::Failed, "data"=> "your request don't have some parameter."];
            $response_code = Response::HTTP_BAD_REQUEST;
        }
        return  response() ->json($response)
            ->setStatusCode($response_code)
            ->header('Content-Type', 'application/json');
    }
}
